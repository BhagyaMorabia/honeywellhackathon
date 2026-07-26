"""Entity profile builder — creates persistent behavioral fingerprints for 600 entities.

Design decisions that make this data defensible:
- Von Mises distribution for login hours (circular — 23:59 and 00:01 are close)
- Zipf-weighted resource catalog (some resources are popular, some are personal)
- Log-normal session durations (realistic long-tail)
- Each entity gets a stable home geo, auth method, and device fingerprint
- Secondary geos assigned to 30% of users (conference travel, VPN)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

from sentinel.data.geo import CITY_DATABASE
from sentinel.utils.logger import get_logger

log = get_logger(__name__)

# ---------- Resource catalog (Zipf-weighted) ----------

RESOURCE_CATALOG: list[str] = [
    # Common shared resources (high frequency in Zipf)
    "file://shared/reports/quarterly.xlsx",
    "https://intranet.corp/dashboard",
    "https://mail.corp/inbox",
    "https://wiki.corp/home",
    "db://prod/users/read",
    "https://jira.corp/board",
    "https://slack.corp/general",
    "file://shared/templates/",
    # Medium-frequency resources
    "db://prod/analytics/query",
    "db://prod/orders/read",
    "https://vpn.corp/connect",
    "https://gitlab.corp/repos",
    "file://shared/finance/budget.xlsx",
    "https://hr.corp/timesheet",
    "api://internal/auth/validate",
    "https://monitoring.corp/grafana",
    "db://prod/inventory/read",
    "https://confluence.corp/docs",
    "file://shared/engineering/specs",
    "https://s3.corp/data-lake/read",
    # Low-frequency / sensitive resources
    "db://prod/users/admin",
    "db://prod/payments/write",
    "api://internal/deploy/trigger",
    "file://secure/credentials/vault",
    "db://prod/audit/logs",
    "https://admin.corp/user-mgmt",
    "api://internal/keys/rotate",
    "db://prod/pii/export",
    "https://firewall.corp/rules",
    "api://scada/plc/read",
    "api://scada/plc/write",
    "api://iot/edge-gateway/config",
    "api://iot/sensor-telemetry/stream",
    "db://ot/historian/query",
    "https://hmi.factory/control-panel",
    # OT / IoT resources (Honeywell tie-in — domain-agnostic)
    "api://ot/dcs/setpoint",
    "api://ot/safety-system/status",
    "modbus://plc-01/register/read",
    "modbus://plc-02/register/write",
    "opcua://server/tag/read",
]

# Command vocabulary for privileged sessions
COMMAND_VOCABULARY: list[str] = [
    "login", "logout", "read_file", "write_file", "delete_file",
    "list_dir", "query_db", "export_data", "create_user", "modify_perms",
    "restart_service", "deploy_app", "rotate_keys", "view_logs",
    "download_report", "upload_data", "run_script", "ssh_connect",
    "rdp_connect", "vpn_connect", "modify_firewall", "backup_db",
    "restore_db", "audit_check", "scan_network", "update_firmware",
    "read_sensor", "write_setpoint", "acknowledge_alarm", "calibrate_device",
]

OS_OPTIONS: list[str] = [
    "Windows 11", "Windows 10", "macOS 14", "macOS 13",
    "Ubuntu 22.04", "Ubuntu 24.04", "RHEL 9", "CentOS Stream 9",
    "iOS 18", "Android 15", "FreeRTOS", "VxWorks",
]

PROTOCOL_OPTIONS: list[str] = [
    "HTTPS", "SSH", "RDP", "Modbus/TCP", "OPC-UA", "MQTT", "CoAP", "WireGuard",
]

FIRMWARE_OPTIONS: list[str] = [
    "v1.0.0", "v1.1.3", "v2.0.1", "v2.3.0", "v3.0.0-beta",
    "v3.1.2", "v4.0.0", "v4.2.1", "v5.0.0-rc1",
]


def _zipf_resource_set(
    rng: np.random.Generator, n_resources: int, catalog: list[str]
) -> list[str]:
    """Select resources with Zipf-weighted probability (power law).

    High-ranked resources (shared files, intranet) are selected more often.
    Low-ranked resources (admin panels, SCADA) are rare.
    """
    n = len(catalog)
    weights = 1.0 / np.arange(1, n + 1) ** 0.8  # Zipf exponent 0.8
    weights /= weights.sum()
    indices = rng.choice(n, size=min(n_resources, n), replace=False, p=weights)
    return [catalog[i] for i in indices]


def make_entity_profiles(
    n_users: int = 400,
    n_edge_devices: int = 150,
    n_service_accounts: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate persistent behavioral profiles for all entities.

    Each entity gets a stable fingerprint that defines their "normal" behavior.
    The generator will sample from these profiles when creating normal events.

    Args:
        n_users: Number of user entities.
        n_edge_devices: Number of edge device entities.
        n_service_accounts: Number of service account entities.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with one row per entity, containing all profile fields.
    """
    fake = Faker()
    Faker.seed(seed)
    rng = np.random.default_rng(seed)

    total = n_users + n_edge_devices + n_service_accounts
    log.info("generating_entity_profiles", total=total)

    entities: list[dict] = []
    for i in range(total):
        # Determine entity type
        if i < n_users:
            etype = "user"
        elif i < n_users + n_edge_devices:
            etype = "edge_device"
        else:
            etype = "service_account"

        # Assign home city
        home_city = rng.choice(CITY_DATABASE)

        # 30% of users have a secondary geo (travel, VPN)
        secondary_lat, secondary_lon = None, None
        if etype == "user" and rng.random() < 0.30:
            sec_city = rng.choice(CITY_DATABASE)
            secondary_lat = float(sec_city["lat"])
            secondary_lon = float(sec_city["lon"])

        # Von Mises center for login hours depends on entity type
        if etype == "user":
            hour_mean = float(rng.uniform(7, 19))  # daytime workers
            hour_std = float(rng.uniform(1.0, 3.0))
        elif etype == "service_account":
            hour_mean = 12.0  # service accounts are ~uniform
            hour_std = 6.0
        else:  # edge_device
            hour_mean = 12.0  # devices report round-the-clock
            hour_std = 5.0

        # Resource set — Zipf-weighted
        n_res = int(rng.integers(5, 16))
        if etype == "edge_device":
            # Edge devices access IoT/OT resources more
            ot_resources = [r for r in RESOURCE_CATALOG if "iot" in r or "scada" in r or "ot" in r
                           or "modbus" in r or "opcua" in r or "hmi" in r]
            it_resources = [r for r in RESOURCE_CATALOG if r not in ot_resources]
            res_set = list(rng.choice(ot_resources, size=min(3, len(ot_resources)), replace=False))
            res_set += list(rng.choice(it_resources, size=min(n_res - 3, len(it_resources)),
                                       replace=False))
        else:
            res_set = _zipf_resource_set(rng, n_res, RESOURCE_CATALOG)

        # Device fingerprint
        if etype == "edge_device":
            os_choice = rng.choice(["FreeRTOS", "VxWorks", "Ubuntu 22.04"])
            proto = rng.choice(["Modbus/TCP", "OPC-UA", "MQTT", "CoAP"])
        elif etype == "service_account":
            os_choice = rng.choice(["Ubuntu 22.04", "Ubuntu 24.04", "RHEL 9", "CentOS Stream 9"])
            proto = rng.choice(["HTTPS", "SSH"])
        else:
            os_choice = rng.choice(OS_OPTIONS[:8])  # desktop/mobile OS
            proto = rng.choice(["HTTPS", "SSH", "RDP", "WireGuard"])

        # Auth method — weighted by entity type
        if etype == "edge_device":
            auth = rng.choice(["certificate", "token"], p=[0.7, 0.3])
        elif etype == "service_account":
            auth = rng.choice(["token", "certificate"], p=[0.6, 0.4])
        else:
            auth = rng.choice(
                ["password", "token", "certificate", "biometric"],
                p=[0.50, 0.30, 0.15, 0.05],
            )

        # Typical commands — varies by entity type
        n_cmds = int(rng.integers(5, 15))
        if etype == "edge_device":
            cmd_pool = [c for c in COMMAND_VOCABULARY if c in [
                "login", "logout", "read_sensor", "write_setpoint",
                "acknowledge_alarm", "calibrate_device", "update_firmware",
                "view_logs",
            ]]
        elif etype == "service_account":
            cmd_pool = [c for c in COMMAND_VOCABULARY if c in [
                "login", "logout", "query_db", "export_data", "run_script",
                "deploy_app", "restart_service", "backup_db", "view_logs",
            ]]
        else:
            cmd_pool = COMMAND_VOCABULARY
        typical_cmds = list(rng.choice(cmd_pool, size=min(n_cmds, len(cmd_pool)), replace=False))

        entities.append({
            "entity_id": fake.uuid4(),
            "entity_type": etype,
            "home_lat": float(home_city["lat"]),
            "home_lon": float(home_city["lon"]),
            "secondary_lat": secondary_lat,
            "secondary_lon": secondary_lon,
            "typical_hour_mean": hour_mean,
            "typical_hour_std": hour_std,
            "resource_set": res_set,
            "session_duration_mean_log": float(rng.uniform(3.0, 6.5)),  # log-seconds
            "session_duration_std_log": float(rng.uniform(0.2, 0.6)),
            "auth_method": auth,
            "device_os": os_choice,
            "device_firmware": rng.choice(FIRMWARE_OPTIONS),
            "device_mac": fake.mac_address(),
            "device_protocol": proto,
            "avg_daily_events": float(rng.uniform(3, 15)),
            "bytes_mean": int(rng.integers(1000, 50000)),
            "bytes_std": int(rng.integers(500, 10000)),
            "typical_commands": typical_cmds,
        })

    df = pd.DataFrame(entities)
    log.info(
        "profiles_generated",
        users=n_users,
        edge_devices=n_edge_devices,
        service_accounts=n_service_accounts,
        total=len(df),
    )
    return df
