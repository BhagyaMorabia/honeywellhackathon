"""Attack pattern injection engine — injects 7 attack types into normal traffic.

Each attack is a function that takes an entity profile and deliberately violates
one or two behavioral properties to create a realistic-but-anomalous event.

Critical design principle: inject NOISE into normal data too, so anomalies
are NOT trivially separable by a single column. A judge who asks "what if I
set every feature to the mean except one — does your model still catch it?"
should get a credible answer.

MITRE ATT&CK mappings:
  brute_force       → T1110
  impossible_travel → T1078
  credential_stuffing → T1110.004
  lateral_movement  → T1021
  device_spoofing   → T1036
  low_and_slow      → T1048
  insider_drift     → T1078
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from sentinel.data.geo import CITY_DATABASE, get_distant_city, haversine_km
from sentinel.data.profiles import COMMAND_VOCABULARY, RESOURCE_CATALOG
from sentinel.utils.logger import get_logger

log = get_logger(__name__)
fake = Faker()


def inject_brute_force(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
    n_attempts: int = 25,
    window_minutes: int = 5,
) -> list[dict]:
    """Rapid repeated failed-auth attempts from one source in a short window.

    Pattern: 20-40 failed logins in 5 minutes, then 1 success (compromised).
    MITRE: T1110
    """
    events = []
    source_ip = fake.ipv4()
    for i in range(n_attempts):
        ts = base_ts + timedelta(seconds=int(rng.integers(0, window_minutes * 60)))
        is_last = i == n_attempts - 1
        events.append({
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type,
            "timestamp": ts,
            "source_ip": source_ip,
            "geo_lat": entity.home_lat + float(rng.normal(0, 0.01)),
            "geo_lon": entity.home_lon + float(rng.normal(0, 0.01)),
            "geo_city": "Unknown",
            "geo_country": "Unknown",
            "resource_accessed": "https://auth.corp/login",
            "auth_method": "password",
            "auth_success": is_last,  # last attempt succeeds
            "session_duration": float(rng.uniform(0.5, 3.0)) if is_last else 0.0,
            "command_sequence": ["login"] if is_last else ["login_failed"],
            "device_os": entity.device_os,
            "device_firmware": entity.device_firmware,
            "device_mac": entity.device_mac,
            "device_protocol": entity.device_protocol,
            "bytes_transferred": int(rng.integers(50, 200)),
            "label": "brute_force",
        })
    return events


def inject_impossible_travel(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
) -> list[dict]:
    """Same entity logging in from geographically distant locations within implausible time.

    Pattern: Login from home, then login from 5000+ km away within 30 minutes.
    MITRE: T1078
    """
    # First event: normal location
    ev1 = {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "timestamp": base_ts,
        "source_ip": fake.ipv4(),
        "geo_lat": entity.home_lat,
        "geo_lon": entity.home_lon,
        "geo_city": "Home",
        "geo_country": "Home",
        "resource_accessed": rng.choice(entity.resource_set) if isinstance(entity.resource_set, list) else entity.resource_set,
        "auth_method": entity.auth_method,
        "auth_success": True,
        "session_duration": float(np.exp(rng.normal(entity.session_duration_mean_log, 0.3))),
        "command_sequence": ["login", "read_file"],
        "device_os": entity.device_os,
        "device_firmware": entity.device_firmware,
        "device_mac": entity.device_mac,
        "device_protocol": entity.device_protocol,
        "bytes_transferred": int(rng.integers(1000, 10000)),
        "label": "impossible_travel",
    }

    # Second event: distant location, 15-45 min later
    distant = get_distant_city(entity.home_lat, entity.home_lon, min_distance_km=3000)
    gap_minutes = int(rng.integers(15, 45))
    ev2 = {
        **ev1,
        "timestamp": base_ts + timedelta(minutes=gap_minutes),
        "source_ip": fake.ipv4(),
        "geo_lat": float(distant["lat"]),
        "geo_lon": float(distant["lon"]),
        "geo_city": str(distant["city"]),
        "geo_country": str(distant["country"]),
    }

    return [ev1, ev2]


def inject_credential_stuffing(
    entities_df: pd.DataFrame,
    base_ts: datetime,
    rng: np.random.Generator,
    n_targets: int = 30,
) -> list[dict]:
    """Many entity_ids attempted from few source_ips, high failure rate.

    Pattern: Single IP tries 30+ accounts with 85%+ failure rate.
    MITRE: T1110.004
    """
    source_ip = fake.ipv4()
    targets = entities_df.sample(n=min(n_targets, len(entities_df)), random_state=int(rng.integers(0, 10000)))
    events = []
    for _, entity in targets.iterrows():
        ts = base_ts + timedelta(seconds=int(rng.integers(0, 900)))  # within 15 min
        events.append({
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type,
            "timestamp": ts,
            "source_ip": source_ip,
            "geo_lat": float(rng.uniform(-60, 60)),
            "geo_lon": float(rng.uniform(-180, 180)),
            "geo_city": "Unknown",
            "geo_country": "Unknown",
            "resource_accessed": "https://auth.corp/login",
            "auth_method": "password",
            "auth_success": bool(rng.random() > 0.85),  # ~15% success rate
            "session_duration": 0.0,
            "command_sequence": ["login_attempt"],
            "device_os": rng.choice(["Windows 10", "Windows 11", "macOS 14"]),
            "device_firmware": "v1.0.0",
            "device_mac": fake.mac_address(),
            "device_protocol": "HTTPS",
            "bytes_transferred": int(rng.integers(50, 300)),
            "label": "credential_stuffing",
        })
    return events


def inject_lateral_movement(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
    n_new_resources: int = 8,
) -> list[dict]:
    """Compromised entity accessing unusual sequence/breadth of resources never touched before.

    Pattern: Entity suddenly accesses 5-10 resources it has never used, in rapid sequence.
    MITRE: T1021
    """
    # Pick resources NOT in the entity's normal set
    entity_res = set(entity.resource_set) if isinstance(entity.resource_set, list) else set()
    novel_resources = [r for r in RESOURCE_CATALOG if r not in entity_res]
    if len(novel_resources) < n_new_resources:
        novel_resources = list(RESOURCE_CATALOG)
    selected = list(rng.choice(novel_resources, size=min(n_new_resources, len(novel_resources)),
                                replace=False))

    events = []
    for i, resource in enumerate(selected):
        ts = base_ts + timedelta(minutes=i * int(rng.integers(2, 10)))
        events.append({
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type,
            "timestamp": ts,
            "source_ip": fake.ipv4(),
            "geo_lat": entity.home_lat + float(rng.normal(0, 0.02)),
            "geo_lon": entity.home_lon + float(rng.normal(0, 0.02)),
            "geo_city": "Internal",
            "geo_country": "Internal",
            "resource_accessed": resource,
            "auth_method": entity.auth_method,
            "auth_success": True,
            "session_duration": float(rng.uniform(30, 300)),
            "command_sequence": list(rng.choice(
                ["ssh_connect", "list_dir", "read_file", "export_data", "query_db",
                 "download_report", "scan_network", "modify_perms"],
                size=int(rng.integers(3, 7)),
                replace=False,
            )),
            "device_os": entity.device_os,
            "device_firmware": entity.device_firmware,
            "device_mac": entity.device_mac,
            "device_protocol": entity.device_protocol,
            "bytes_transferred": int(rng.integers(5000, 100000)),
            "label": "lateral_movement",
        })
    return events


def inject_device_spoofing(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
) -> list[dict]:
    """Device_id reappearing with a mismatched fingerprint (different OS/MAC).

    Pattern: Known device suddenly has different OS and MAC address.
    MITRE: T1036
    """
    return [{
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "timestamp": base_ts,
        "source_ip": fake.ipv4(),
        "geo_lat": entity.home_lat + float(rng.normal(0, 0.03)),
        "geo_lon": entity.home_lon + float(rng.normal(0, 0.03)),
        "geo_city": "Unknown",
        "geo_country": "Unknown",
        "resource_accessed": rng.choice(entity.resource_set) if isinstance(entity.resource_set, list) else "https://intranet.corp/dashboard",
        "auth_method": entity.auth_method,
        "auth_success": True,
        "session_duration": float(np.exp(rng.normal(entity.session_duration_mean_log, 0.3))),
        "command_sequence": ["login", "read_file"],
        # Spoofed fingerprint — different from entity's real device
        "device_os": rng.choice([o for o in ["Windows 11", "macOS 14", "Ubuntu 22.04", "Android 15"]
                                  if o != entity.device_os]),
        "device_firmware": "v99.0.0-spoofed",
        "device_mac": fake.mac_address(),  # different MAC
        "device_protocol": entity.device_protocol,
        "bytes_transferred": int(rng.integers(500, 5000)),
        "label": "device_spoofing",
    }]


def inject_low_and_slow(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
    n_days: int = 7,
    events_per_day: int = 2,
) -> list[dict]:
    """Gradual, small, off-hours resource access building up over days/weeks.

    Pattern: Small data transfers at 2-4 AM over many days, gradually increasing volume.
    MITRE: T1048
    """
    events = []
    for day in range(n_days):
        for _ in range(events_per_day):
            hour = int(rng.integers(1, 5))  # 1-4 AM (off-hours)
            minute = int(rng.integers(0, 60))
            ts = base_ts + timedelta(days=day, hours=hour, minutes=minute)
            # Gradually increasing bytes transferred
            base_bytes = 500 + day * 200
            events.append({
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "timestamp": ts,
                "source_ip": fake.ipv4(),
                "geo_lat": entity.home_lat + float(rng.normal(0, 0.02)),
                "geo_lon": entity.home_lon + float(rng.normal(0, 0.02)),
                "geo_city": "Internal",
                "geo_country": "Internal",
                "resource_accessed": rng.choice(
                    ["db://prod/pii/export", "file://secure/credentials/vault",
                     "db://prod/payments/write", "https://s3.corp/data-lake/read"]
                ),
                "auth_method": entity.auth_method,
                "auth_success": True,
                "session_duration": float(rng.uniform(60, 600)),
                "command_sequence": ["login", "query_db", "export_data", "logout"],
                "device_os": entity.device_os,
                "device_firmware": entity.device_firmware,
                "device_mac": entity.device_mac,
                "device_protocol": entity.device_protocol,
                "bytes_transferred": int(rng.integers(base_bytes, base_bytes + 1000)),
                "label": "low_and_slow",
            })
    return events


def inject_insider_drift(
    entity: pd.Series,
    base_ts: datetime,
    rng: np.random.Generator,
    n_days: int = 14,
) -> list[dict]:
    """Legitimate entity slowly expanding privilege/resource footprint — ambiguous edge case.

    Pattern: Gradual, plausible expansion of accessed resources over 2 weeks.
    Used for false-positive tuning — this should be the HARDEST for the model.
    MITRE: T1078
    """
    entity_res = set(entity.resource_set) if isinstance(entity.resource_set, list) else set()
    novel_resources = [r for r in RESOURCE_CATALOG if r not in entity_res]
    events = []

    for day in range(n_days):
        # Add 1 new resource every 2-3 days
        if day % rng.integers(2, 4) == 0 and novel_resources:
            new_res = novel_resources.pop(0)
        else:
            new_res = rng.choice(list(entity_res)) if entity_res else RESOURCE_CATALOG[0]

        # Normal-looking timing (during work hours)
        hour = int(np.clip(rng.normal(entity.typical_hour_mean, entity.typical_hour_std), 6, 20))
        ts = base_ts + timedelta(days=day, hours=hour, minutes=int(rng.integers(0, 60)))

        events.append({
            "entity_id": entity.entity_id,
            "entity_type": entity.entity_type,
            "timestamp": ts,
            "source_ip": fake.ipv4(),
            "geo_lat": entity.home_lat + float(rng.normal(0, 0.03)),
            "geo_lon": entity.home_lon + float(rng.normal(0, 0.03)),
            "geo_city": "Office",
            "geo_country": "Office",
            "resource_accessed": new_res,
            "auth_method": entity.auth_method,
            "auth_success": True,
            "session_duration": float(np.exp(rng.normal(entity.session_duration_mean_log, 0.4))),
            "command_sequence": list(rng.choice(
                entity.typical_commands if isinstance(entity.typical_commands, list)
                and len(entity.typical_commands) > 0
                else ["login", "read_file", "query_db"],
                size=int(rng.integers(2, 5)),
                replace=True,
            )),
            "device_os": entity.device_os,
            "device_firmware": entity.device_firmware,
            "device_mac": entity.device_mac,
            "device_protocol": entity.device_protocol,
            "bytes_transferred": int(rng.integers(
                max(1, entity.bytes_mean - entity.bytes_std),
                entity.bytes_mean + entity.bytes_std,
            )),
            "label": "insider_drift",
        })
    return events
