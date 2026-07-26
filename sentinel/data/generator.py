"""Main synthetic data generator — orchestrates entity profiles, normal traffic, and attack injection.

This is the critical first module. Everything else blocks on it.
Outputs:
  - access_logs.csv: All events WITHOUT labels (what the pipeline sees)
  - hidden_labels.csv: event_id → true label (for evaluation ONLY)
  - entity_profiles.csv: Per-entity behavioral fingerprints

Design decisions:
  - Von Mises distribution for login hours (circular)
  - Zipf-weighted resource selection (realistic access patterns)
  - 2% natural auth failure in normal data (prevents trivial separability)
  - 5% of users have secondary geos (travel/VPN noise)
  - Temporal train/test split: days 1-30 / days 31-45
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from sentinel.data.attacks import (
    inject_brute_force,
    inject_credential_stuffing,
    inject_device_spoofing,
    inject_impossible_travel,
    inject_insider_drift,
    inject_lateral_movement,
    inject_low_and_slow,
)
from sentinel.data.geo import add_geo_noise
from sentinel.data.profiles import COMMAND_VOCABULARY, make_entity_profiles
from sentinel.utils.logger import get_logger

log = get_logger(__name__)
fake = Faker()


def _sample_von_mises_hour(mean: float, std: float, rng: np.random.Generator) -> float:
    """Sample hour-of-day using Von Mises (circular normal) distribution.

    This ensures 23:59 and 00:01 are treated as close together,
    unlike naive Gaussian on hour-of-day which wraps incorrectly at midnight.

    Args:
        mean: Center of the distribution (hours, 0-24).
        std: Spread parameter (lower = tighter concentration).
        rng: NumPy random generator.

    Returns:
        Hour as float in [0, 24).
    """
    # Convert hours to radians (0-24h → 0-2π)
    mu = (mean / 24.0) * 2 * np.pi
    # Convert std to kappa (concentration): higher kappa = tighter
    kappa = max(0.5, 1.0 / (std ** 2 + 0.01))
    angle = rng.vonmises(mu, kappa)
    # Convert back to hours
    hour = (angle / (2 * np.pi)) * 24.0
    return hour % 24.0


def _sample_normal_event(
    entity: pd.Series,
    day: int,
    base_date: datetime,
    rng: np.random.Generator,
    normal_failure_rate: float = 0.02,
    secondary_geo_rate: float = 0.05,
) -> dict:
    """Generate a single normal event for an entity.

    Includes realistic noise:
    - 2% of normal events have auth_success=False (so brute_force isn't trivially separable)
    - 5% of users with secondary geos occasionally login from secondary location
    """
    hour = _sample_von_mises_hour(entity.typical_hour_mean, entity.typical_hour_std, rng)
    hour_int = int(hour) % 24
    minute = int((hour - hour_int) * 60) % 60
    second = int(rng.integers(0, 60))

    ts = base_date + timedelta(days=day, hours=hour_int, minutes=minute, seconds=second)

    # Geo: usually home, sometimes secondary (travel noise)
    use_secondary = (
        entity.secondary_lat is not None
        and not pd.isna(entity.secondary_lat)
        and rng.random() < secondary_geo_rate
    )
    if use_secondary:
        lat, lon = add_geo_noise(entity.secondary_lat, entity.secondary_lon, 0.05, rng)
    else:
        lat, lon = add_geo_noise(entity.home_lat, entity.home_lon, 0.05, rng)

    # Resource: from entity's personal set
    res_set = entity.resource_set if isinstance(entity.resource_set, list) else ["https://intranet.corp/dashboard"]
    resource = rng.choice(res_set)

    # Commands: from entity's typical set
    cmd_set = entity.typical_commands if isinstance(entity.typical_commands, list) and len(entity.typical_commands) > 0 else ["login", "read_file"]
    n_cmds = int(rng.integers(1, min(5, len(cmd_set) + 1)))
    commands = list(rng.choice(cmd_set, size=n_cmds, replace=True))

    # Session duration: log-normal
    duration = float(np.exp(rng.normal(entity.session_duration_mean_log,
                                         entity.session_duration_std_log)))

    # Auth noise: 2% of normal events fail (prevents brute_force from being trivially separable)
    auth_success = bool(rng.random() > normal_failure_rate)

    # Bytes transferred: normal distribution around entity's mean
    bytes_tx = max(0, int(rng.normal(entity.bytes_mean, entity.bytes_std)))

    return {
        "event_id": fake.uuid4(),
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "timestamp": ts,
        "source_ip": fake.ipv4(),
        "geo_lat": lat,
        "geo_lon": lon,
        "geo_city": "",
        "geo_country": "",
        "resource_accessed": resource,
        "auth_method": entity.auth_method,
        "auth_success": auth_success,
        "session_duration": duration,
        "command_sequence": commands,
        "device_os": entity.device_os,
        "device_firmware": entity.device_firmware,
        "device_mac": entity.device_mac,
        "device_protocol": entity.device_protocol,
        "bytes_transferred": bytes_tx,
        "label": "normal",
    }


def generate_dataset(
    n_users: int = 400,
    n_edge_devices: int = 150,
    n_service_accounts: int = 50,
    simulation_days: int = 45,
    seed: int = 42,
    attack_rates: dict[str, float] | None = None,
    output_dir: str = "data/synthetic_logs",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate the complete synthetic dataset.

    Steps:
    1. Create entity profiles
    2. Generate normal traffic for all entities across all days
    3. Inject attacks at specified rates
    4. Split access_logs (no labels) from hidden_labels (event_id → label)
    5. Save to CSV

    Args:
        n_users: Number of user entities.
        n_edge_devices: Number of edge device entities.
        n_service_accounts: Number of service account entities.
        simulation_days: Total days to simulate.
        seed: Random seed.
        attack_rates: Dict of attack_type → fraction of total events.
        output_dir: Directory to save CSVs.

    Returns:
        Tuple of (access_logs_df, hidden_labels_df, entity_profiles_df).
    """
    rng = np.random.default_rng(seed)
    Faker.seed(seed)

    if attack_rates is None:
        attack_rates = {
            "brute_force": 0.003,
            "impossible_travel": 0.002,
            "credential_stuffing": 0.003,
            "lateral_movement": 0.002,
            "device_spoofing": 0.001,
            "low_and_slow": 0.002,
            "insider_drift": 0.002,
        }

    # Step 1: Entity profiles
    log.info("step_1_generating_profiles")
    profiles_df = make_entity_profiles(n_users, n_edge_devices, n_service_accounts, seed)

    # Step 2: Normal traffic
    log.info("step_2_generating_normal_traffic", days=simulation_days)
    base_date = datetime(2025, 1, 1)
    all_events: list[dict] = []

    for _, entity in profiles_df.iterrows():
        for day in range(simulation_days):
            current_date = base_date + timedelta(days=day)
            is_weekend = current_date.weekday() >= 5
            
            # Poisson-distributed event count per day
            expected_events = entity.avg_daily_events
            
            # Massive realism edge case: Humans don't work much on weekends.
            # Edge devices and service accounts run 24/7.
            if is_weekend and entity.entity_type == "user":
                expected_events *= 0.05  # 95% drop in human traffic on weekends
                
            n_events = int(rng.poisson(expected_events))
            # Only guarantee at least 1 event for non-users or weekdays to allow true weekend silence
            if not (is_weekend and entity.entity_type == "user"):
                n_events = max(1, n_events)
                
            for _ in range(n_events):
                event = _sample_normal_event(entity, day, base_date, rng)
                all_events.append(event)

    log.info("normal_events_generated", count=len(all_events))

    # Step 3: Inject attacks
    log.info("step_3_injecting_attacks")
    total_events = len(all_events)
    attack_events: list[dict] = []

    # Users only for user-targeted attacks
    user_profiles = profiles_df[profiles_df.entity_type == "user"]

    for attack_type, rate in attack_rates.items():
        n_attack_events = max(1, int(total_events * rate))
        log.info("injecting_attack", type=attack_type, target_events=n_attack_events)

        injected = 0
        max_attempts = n_attack_events * 3

        for attempt in range(max_attempts):
            if injected >= n_attack_events:
                break

            day = int(rng.integers(0, simulation_days))
            ts = base_date + timedelta(days=day, hours=int(rng.integers(0, 24)),
                                       minutes=int(rng.integers(0, 60)))
            entity = user_profiles.sample(1, random_state=int(rng.integers(0, 100000))).iloc[0]

            if attack_type == "brute_force":
                events = inject_brute_force(entity, ts, rng,
                                           n_attempts=int(rng.integers(15, 40)))
            elif attack_type == "impossible_travel":
                events = inject_impossible_travel(entity, ts, rng)
            elif attack_type == "credential_stuffing":
                events = inject_credential_stuffing(profiles_df, ts, rng,
                                                    n_targets=int(rng.integers(20, 50)))
            elif attack_type == "lateral_movement":
                events = inject_lateral_movement(entity, ts, rng,
                                                 n_new_resources=int(rng.integers(5, 12)))
            elif attack_type == "device_spoofing":
                # Can target any entity type
                entity = profiles_df.sample(1, random_state=int(rng.integers(0, 100000))).iloc[0]
                events = inject_device_spoofing(entity, ts, rng)
            elif attack_type == "low_and_slow":
                events = inject_low_and_slow(entity, ts, rng,
                                            n_days=int(rng.integers(5, 10)))
            elif attack_type == "insider_drift":
                events = inject_insider_drift(entity, ts, rng,
                                             n_days=int(rng.integers(10, 20)))
            else:
                continue

            # Add event_ids to attack events
            for ev in events:
                ev["event_id"] = fake.uuid4()
                attack_events.append(ev)
                injected += 1

        log.info("attack_injected", type=attack_type, actual_events=injected)

    # Combine normal + attack events
    all_events.extend(attack_events)
    events_df = pd.DataFrame(all_events)

    # Sort by timestamp (critical for temporal ordering)
    events_df = events_df.sort_values("timestamp").reset_index(drop=True)

    # Step 4: Separate access_logs (no labels) from hidden_labels
    hidden_labels_df = events_df[["event_id", "label"]].copy()
    access_logs_df = events_df.drop(columns=["label"])

    # Step 5: Save to CSV
    os.makedirs(output_dir, exist_ok=True)

    access_logs_path = os.path.join(output_dir, "access_logs.csv")
    hidden_labels_path = os.path.join(output_dir, "hidden_labels.csv")
    profiles_path = os.path.join(output_dir, "entity_profiles.csv")

    access_logs_df.to_csv(access_logs_path, index=False)
    hidden_labels_df.to_csv(hidden_labels_path, index=False)
    profiles_df.to_csv(profiles_path, index=False)

    # Stats
    total = len(events_df)
    n_anomalies = (events_df.label != "normal").sum()
    anomaly_rate = n_anomalies / total * 100 if total > 0 else 0

    log.info(
        "dataset_generated",
        total_events=total,
        anomaly_events=int(n_anomalies),
        anomaly_rate=f"{anomaly_rate:.2f}%",
        output_dir=output_dir,
    )

    # Per-type breakdown
    for label, count in events_df.label.value_counts().items():
        log.info("label_distribution", label=label, count=int(count),
                 pct=f"{count/total*100:.2f}%")

    return access_logs_df, hidden_labels_df, profiles_df


if __name__ == "__main__":
    from sentinel.utils.logger import setup_logging
    setup_logging("INFO")
    generate_dataset()
