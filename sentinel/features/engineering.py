"""Feature engineering — computes all 27+ features from raw access events.

Features are organized into 5 groups:
  1. Temporal (7): hour sin/cos, day_of_week, is_weekend, is_work_hours, time_since_last, frequency
  2. Behavioral (10): auth rates, resource diversity/novelty, session z-scores, bytes z-scores, etc.
  3. Geo-Spatial (5): velocity, distance from home, impossible travel flag, new geo
  4. Device (3): fingerprint mismatch, new device, protocol mismatch
  5. Cold-Start Meta (2): maturity weight, is_cold_start

Also includes frequency encoding for high-cardinality categoricals (source_ip, resource_accessed)
to avoid memory-bloating one-hot encoding — XGBoost thrives on these dense continuous features.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from sentinel.data.geo import haversine_km
from sentinel.features.profiles import EntityProfileStore
from sentinel.utils.logger import get_logger

log = get_logger(__name__)


class FeatureEngine:
    """Computes all engineered features for each event in the access log.

    Maintains rolling state for:
    - Per-entity last event (for velocity, time_since_last)
    - Per-entity accessed resources (for novelty detection)
    - Per-source-IP event counts (for credential stuffing signal)
    - Frequency counts for high-cardinality categoricals
    """

    def __init__(self, profile_store: EntityProfileStore | None = None):
        """Initialize the feature engine.

        Args:
            profile_store: EntityProfileStore for z-score computation and cold-start.
                          If None, a new one is created with default params.
        """
        self.profile_store = profile_store or EntityProfileStore()
        self.entity_last_event: dict[str, dict] = {}
        self.entity_resource_history: dict[str, set[str]] = defaultdict(set)
        self.entity_device_history: dict[str, set[str]] = defaultdict(set)
        self.entity_auth_history: dict[str, list[bool]] = defaultdict(list)
        self.ip_entity_map: dict[str, set[str]] = defaultdict(set)
        self.ip_event_times: dict[str, list[float]] = defaultdict(list)

        # Frequency counters for frequency encoding
        self.resource_freq: dict[str, int] = defaultdict(int)
        self.ip_freq: dict[str, int] = defaultdict(int)
        self.total_events_processed: int = 0
        
        # Generalization Histories
        self.entity_mac_history: dict[str, set[str]] = defaultdict(set)
        self.entity_resource_timestamps: dict[str, list[float]] = defaultdict(list)

    def compute_features(self, events_df: pd.DataFrame) -> pd.DataFrame:
        """Compute all features for a DataFrame of events.

        Events MUST be sorted by timestamp (temporal order is critical).

        Args:
            events_df: DataFrame with columns matching AccessEvent schema (minus label).

        Returns:
            DataFrame with one row per event, all 27+ engineered features as columns.
        """
        log.info("computing_features", n_events=len(events_df))
        feature_rows: list[dict] = []

        for event in events_df.itertuples(index=False):
            features = self._compute_single_event(event)
            feature_rows.append(features)

        features_df = pd.DataFrame(feature_rows)
        log.info("features_computed", n_features=len(features_df.columns), n_rows=len(features_df))
        return features_df

    def _compute_single_event(self, event: pd.Series) -> dict[str, float]:
        """Compute all features for a single event.

        Args:
            event: A single row from the access log DataFrame.

        Returns:
            Dict of feature_name → value.
        """
        entity_id = event.entity_id
        entity_type = event.entity_type
        ts = event.timestamp
        if isinstance(ts, str):
            ts = pd.Timestamp(ts)
        ts_epoch = ts.timestamp() if hasattr(ts, 'timestamp') else 0.0

        features: dict[str, float] = {}

        # ── Temporal features (7) ──────────────────────────────────────
        hour = ts.hour + ts.minute / 60.0 if hasattr(ts, 'hour') else 12.0
        features["hour_sin"] = float(np.sin(2 * np.pi * hour / 24.0))
        features["hour_cos"] = float(np.cos(2 * np.pi * hour / 24.0))
        features["day_of_week"] = float(ts.weekday()) if hasattr(ts, 'weekday') else 0.0
        features["is_weekend"] = 1.0 if features["day_of_week"] >= 5 else 0.0
        features["is_work_hours"] = 1.0 if 8 <= hour <= 18 else 0.0

        # Time since last event (seconds)
        last = self.entity_last_event.get(entity_id)
        if last is not None:
            features["time_since_last"] = max(0, ts_epoch - last["ts_epoch"])
        else:
            features["time_since_last"] = 0.0

        # Session frequency in last hour
        features["session_frequency_1h"] = self._count_recent_events(
            entity_id, ts_epoch, window_seconds=3600
        )

        # ── Behavioral features (10) ──────────────────────────────────
        # Auth failure rate in last 10 min
        self.entity_auth_history[entity_id].append(event.auth_success)
        recent_auths = self.entity_auth_history[entity_id][-50:]  # last 50 events
        n_fails = sum(1 for a in recent_auths if not a)
        features["auth_failure_rate"] = n_fails / max(len(recent_auths), 1)

        # --- Corrected Resource Novelty & History Order ---
        resource = (
            str(event.resource_accessed)
            if hasattr(event, "resource_accessed")
            else ""
        )

        # 1. Check novelty BEFORE adding to history
        known_resources = self.entity_resource_history[entity_id]
        is_novel_resource = resource not in known_resources

        features["resource_novelty"] = 1.0 if is_novel_resource else 0.0

        # 2. Update history AFTER novelty check
        self.entity_resource_history[entity_id].add(resource)
        features["resource_diversity"] = float(
            len(self.entity_resource_history[entity_id])
        )

        # Session duration (raw + z-scored below via profile store)
        session_dur = float(event.session_duration) if hasattr(event, 'session_duration') else 0.0
        features["session_duration_raw"] = session_dur

        # Bytes transferred
        bytes_tx = float(event.bytes_transferred) if hasattr(event, 'bytes_transferred') else 0.0
        features["bytes_transferred_raw"] = bytes_tx

        # Auth method mismatch (different from most common for this entity?)
        features["auth_method_mismatch"] = 0.0  # Will be refined by profile store

        # Command entropy (Shannon entropy of command distribution)
        cmds = event.command_sequence if hasattr(event, 'command_sequence') and isinstance(event.command_sequence, list) else []
        features["command_entropy"] = self._shannon_entropy(cmds)

        # Unique entities per source IP (credential stuffing signal)
        source_ip = str(event.source_ip) if hasattr(event, 'source_ip') else ""
        self.ip_entity_map[source_ip].add(entity_id)
        self.ip_event_times[source_ip].append(ts_epoch)
        features["unique_entities_per_ip"] = float(len(self.ip_entity_map[source_ip]))

        # Off-hours access
        features["is_off_hours"] = 1.0 if (hour < 6 or hour > 22) else 0.0

        # Privilege expansion rate & velocity
        features["privilege_expansion_rate"] = 0.0
        if features["resource_diversity"] > 1:
            features["privilege_expansion_rate"] = 1.0 / features["resource_diversity"]
            
        # Velocity: new resources in the last 7 days
        if features["resource_novelty"] > 0:
            self.entity_resource_timestamps[entity_id].append(ts_epoch)
        
        recent_new_resources = [t for t in self.entity_resource_timestamps[entity_id] if ts_epoch - t <= (7 * 24 * 3600)]
        # Prune old
        self.entity_resource_timestamps[entity_id] = recent_new_resources
        features["privilege_expansion_velocity"] = float(len(recent_new_resources))

        # ── Geo-Spatial features (5) ──────────────────────────────────
        geo_lat = float(event.geo_lat) if hasattr(event, 'geo_lat') else 0.0
        geo_lon = float(event.geo_lon) if hasattr(event, 'geo_lon') else 0.0

        if last is not None:
            dist_km = haversine_km(last["lat"], last["lon"], geo_lat, geo_lon)
            time_hours = max(features["time_since_last"] / 3600, 0.001)
            features["geo_velocity_kmh"] = dist_km / time_hours
        else:
            features["geo_velocity_kmh"] = 0.0

        features["impossible_travel_flag"] = 1.0 if features["geo_velocity_kmh"] > 900 else 0.0

        # Distance from entity's primary geo (if we knew it — proxy: first event location)
        if last is not None:
            features["geo_distance_from_primary"] = haversine_km(
                last.get("first_lat", geo_lat),
                last.get("first_lon", geo_lon),
                geo_lat,
                geo_lon,
            )
        else:
            features["geo_distance_from_primary"] = 0.0

        features["is_new_geo"] = 0.0  # Simplified — would need geo history

        features["geo_anomaly_score"] = (
            0.3 * min(features["geo_velocity_kmh"] / 1000, 1.0)
            + 0.3 * features["impossible_travel_flag"]
            + 0.4 * min(features["geo_distance_from_primary"] / 10000, 1.0)
        )

        # ── Device features (3) ───────────────────────────────────────
        device_mac = str(event.device_mac) if hasattr(event, 'device_mac') else ""
        device_os = str(event.device_os) if hasattr(event, 'device_os') else ""

        self.entity_mac_history[entity_id].add(device_mac)
        features["device_stability_index"] = float(len(self.entity_mac_history[entity_id]))

        known_devices = self.entity_device_history.get(entity_id, set())
        features["new_device_flag"] = 0.0
        device_key = f"{device_os}|{device_mac}"
        features["new_device_flag"] = 1.0 if device_key not in known_devices and len(known_devices) > 0 else 0.0
        features["fingerprint_mismatch"] = features["new_device_flag"]
        features["protocol_mismatch"] = 0.0  # Would need protocol history
        self.entity_device_history[entity_id].add(device_key)

        # ── Frequency encoding for high-cardinality categoricals ──────
        self.total_events_processed += 1
        self.resource_freq[resource] += 1
        self.ip_freq[source_ip] += 1

        features["resource_freq_encoding"] = self.resource_freq[resource] / self.total_events_processed
        features["ip_freq_encoding"] = self.ip_freq[source_ip] / self.total_events_processed

        # ── Cold-Start Meta (2) ───────────────────────────────────────
        weight = self.profile_store.get_maturity_weight(entity_id)
        features["entity_maturity_weight"] = weight
        features["is_cold_start"] = 1.0 if weight < 0.5 else 0.0

        # ── Z-scores via profile store ────────────────────────────────
        profile_features = {
            "session_duration": session_dur,
            "bytes_transferred": bytes_tx,
            "hour": hour,
            "auth_failure_rate": features["auth_failure_rate"],
            "resource_diversity": features["resource_diversity"],
            "geo_velocity_kmh": features["geo_velocity_kmh"],
        }
        z_scores, _ = self.profile_store.score_and_update(
            entity_id, entity_type, profile_features
        )
        for k, v in z_scores.items():
            features[f"{k}_zscore"] = v

        # ── Update last event state ───────────────────────────────────
        first_lat = self.entity_last_event.get(entity_id, {}).get("first_lat", geo_lat)
        first_lon = self.entity_last_event.get(entity_id, {}).get("first_lon", geo_lon)
        self.entity_last_event[entity_id] = {
            "ts_epoch": ts_epoch,
            "lat": geo_lat,
            "lon": geo_lon,
            "first_lat": first_lat,
            "first_lon": first_lon,
        }

        return features

    def _count_recent_events(
        self, entity_id: str, current_ts: float, window_seconds: int = 3600
    ) -> float:
        """Count entity's events in the last `window_seconds`."""
        auths = self.entity_auth_history.get(entity_id, [])
        return float(len(auths))  # Simplified: in production, use time-indexed window

    @staticmethod
    def _shannon_entropy(items: list[str]) -> float:
        """Compute Shannon entropy of a list of items.

        Higher entropy = more diverse command usage.
        """
        if not items:
            return 0.0
        counts: dict[str, int] = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        total = len(items)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        return float(entropy)
