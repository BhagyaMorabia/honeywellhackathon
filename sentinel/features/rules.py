"""Deterministic rule engine — instantly explainable, zero false negatives on known patterns.

Each rule returns None (clean) or a dict with:
  - rule: attack type name
  - detail: human-readable explanation
  - mitre: MITRE ATT&CK technique ID

Rules act as the perimeter WAF equivalent — they catch noisy, volumetric attacks
outright, freeing the ML models to focus on subtle, low-and-slow threats.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd

from sentinel.data.geo import haversine_km
from sentinel.utils.logger import get_logger

log = get_logger(__name__)


class RuleEngine:
    """Deterministic rule-based anomaly detector.

    Maintains rolling windows for:
    - Per-entity auth failures (brute force)
    - Per-IP entity targets (credential stuffing)
    - Per-entity device fingerprints (device spoofing)
    - Per-entity geo history (impossible travel)
    """

    def __init__(
        self,
        brute_force_window_min: int = 10,
        brute_force_min_failures: int = 8,
        impossible_travel_max_kmh: float = 900.0,
        credential_stuffing_window_min: int = 15,
        credential_stuffing_min_targets: int = 15,
        credential_stuffing_min_fail_rate: float = 0.70,
    ):
        """Initialize rule engine with configurable thresholds.

        All thresholds come from config.yaml — no magic numbers.
        """
        self.bf_window = brute_force_window_min
        self.bf_min_fails = brute_force_min_failures
        self.it_max_kmh = impossible_travel_max_kmh
        self.cs_window = credential_stuffing_window_min
        self.cs_min_targets = credential_stuffing_min_targets
        self.cs_min_fail_rate = credential_stuffing_min_fail_rate

        # Rolling state
        self.entity_auth_events: dict[str, list[dict]] = defaultdict(list)
        self.entity_last_geo: dict[str, dict] = {}
        self.entity_device_fingerprints: dict[str, str] = {}
        self.ip_auth_events: dict[str, list[dict]] = defaultdict(list)

    def check_all_rules(self, event: pd.Series) -> list[dict]:
        """Run all rules against a single event.

        Args:
            event: A single row from the access log.

        Returns:
            List of rule hit dicts (empty if no rules fire).
        """
        hits: list[dict] = []

        ts = event.timestamp
        if isinstance(ts, str):
            ts = pd.Timestamp(ts)
        ts_epoch = ts.timestamp() if hasattr(ts, 'timestamp') else 0.0

        entity_id = str(event.entity_id)
        source_ip = str(event.source_ip) if hasattr(event, 'source_ip') else ""

        # Track auth events
        auth_event = {
            "entity_id": entity_id,
            "ts_epoch": ts_epoch,
            "auth_success": bool(event.auth_success),
            "source_ip": source_ip,
        }
        self.entity_auth_events[entity_id].append(auth_event)
        self.ip_auth_events[source_ip].append(auth_event)

        # Rule 1: Brute Force
        bf = self._check_brute_force(entity_id, ts_epoch)
        if bf:
            hits.append(bf)

        # Rule 2: Impossible Travel
        geo_lat = float(event.geo_lat) if hasattr(event, 'geo_lat') else 0.0
        geo_lon = float(event.geo_lon) if hasattr(event, 'geo_lon') else 0.0
        it = self._check_impossible_travel(entity_id, geo_lat, geo_lon, ts_epoch)
        if it:
            hits.append(it)

        # Update last geo
        self.entity_last_geo[entity_id] = {
            "lat": geo_lat, "lon": geo_lon, "ts_epoch": ts_epoch
        }

        # Rule 3: Credential Stuffing
        cs = self._check_credential_stuffing(source_ip, ts_epoch)
        if cs:
            hits.append(cs)

        # Rule 4: Device Spoofing
        device_os = str(event.device_os) if hasattr(event, 'device_os') else ""
        device_mac = str(event.device_mac) if hasattr(event, 'device_mac') else ""
        ds = self._check_device_spoofing(entity_id, device_os, device_mac)
        if ds:
            hits.append(ds)

        return hits

    def _check_brute_force(self, entity_id: str, current_ts: float) -> dict | None:
        """Check for rapid repeated auth failures.

        Pattern: ≥N failed auths from same entity in M minutes.
        """
        window_start = current_ts - self.bf_window * 60
        recent = [
            e for e in self.entity_auth_events[entity_id]
            if e["ts_epoch"] >= window_start and not e["auth_success"]
        ]
        if len(recent) >= self.bf_min_fails:
            return {
                "rule": "brute_force",
                "detail": f"{len(recent)} failed auths in {self.bf_window} min",
                "mitre": "T1110",
                "confidence": min(1.0, len(recent) / (self.bf_min_fails * 2)),
            }
        return None

    def _check_impossible_travel(
        self, entity_id: str, lat: float, lon: float, ts_epoch: float
    ) -> dict | None:
        """Check for geographically implausible travel speed.

        Pattern: Entity appears >900 km/h between consecutive events.
        """
        last = self.entity_last_geo.get(entity_id)
        if last is None:
            return None

        dist = haversine_km(last["lat"], last["lon"], lat, lon)
        hours = (ts_epoch - last["ts_epoch"]) / 3600
        if hours <= 0:
            return None

        speed = dist / hours
        if speed > self.it_max_kmh:
            return {
                "rule": "impossible_travel",
                "detail": f"{dist:.0f} km in {hours:.2f}h ({speed:.0f} km/h)",
                "mitre": "T1078",
                "confidence": min(1.0, speed / (self.it_max_kmh * 3)),
            }
        return None

    def _check_credential_stuffing(self, source_ip: str, current_ts: float) -> dict | None:
        """Check for many unique entities targeted from a single IP.

        Pattern: ≥N unique entities from 1 IP, with ≥M% failure rate.
        """
        window_start = current_ts - self.cs_window * 60
        recent = [e for e in self.ip_auth_events[source_ip] if e["ts_epoch"] >= window_start]
        if len(recent) < self.cs_min_targets:
            return None

        unique_targets = {e["entity_id"] for e in recent}
        if len(unique_targets) < self.cs_min_targets:
            return None

        fails = sum(1 for e in recent if not e["auth_success"])
        fail_rate = fails / max(len(recent), 1)
        if fail_rate >= self.cs_min_fail_rate:
            return {
                "rule": "credential_stuffing",
                "detail": f"{len(unique_targets)} accounts, {fail_rate:.0%} failure from IP {source_ip}",
                "mitre": "T1110.004",
                "confidence": min(1.0, len(unique_targets) / (self.cs_min_targets * 2)),
            }
        return None

    def _check_device_spoofing(
        self, entity_id: str, device_os: str, device_mac: str
    ) -> dict | None:
        """Check for device fingerprint mismatch.

        Pattern: Known device_id with different OS or MAC address.
        """
        device_key = f"{device_os}|{device_mac}"
        known = self.entity_device_fingerprints.get(entity_id)

        if known is None:
            self.entity_device_fingerprints[entity_id] = device_key
            return None

        if known != device_key:
            result = {
                "rule": "device_spoofing",
                "detail": f"Fingerprint mismatch: expected {known}, got {device_key}",
                "mitre": "T1036",
                "confidence": 0.8,
            }
            # Update to new fingerprint (could be legitimate device change)
            self.entity_device_fingerprints[entity_id] = device_key
            return result

        return None

    def get_rule_flags(self, rule_hits: list[dict]) -> dict[str, float]:
        """Convert rule hits to a one-hot feature dict for the fusion classifier.

        Args:
            rule_hits: List of rule hit dicts from check_all_rules.

        Returns:
            Dict with binary flags for each rule type.
        """
        flags = {
            "rule_brute_force": 0.0,
            "rule_impossible_travel": 0.0,
            "rule_credential_stuffing": 0.0,
            "rule_device_spoofing": 0.0,
        }
        for hit in rule_hits:
            rule_name = hit["rule"]
            flags[f"rule_{rule_name}"] = 1.0
        return flags
