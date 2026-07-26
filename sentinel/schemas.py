"""Pydantic v2 schemas — the data contract for the entire pipeline.

Every event, profile, and fingerprint is validated at creation time.
Invalid data fails FAST at ingestion, not silently in the model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------- Enums as Literals (faster than Python enums for Pydantic v2) ----------

EntityType = Literal["user", "service_account", "edge_device"]
AuthMethod = Literal["password", "token", "certificate", "biometric"]
AnomalyLabel = Literal[
    "normal",
    "brute_force",
    "impossible_travel",
    "credential_stuffing",
    "lateral_movement",
    "device_spoofing",
    "low_and_slow",
    "insider_drift",
]

# MITRE ATT&CK mapping for each anomaly type
MITRE_MAPPING: dict[str, str] = {
    "brute_force": "T1110 (Brute Force)",
    "impossible_travel": "T1078 (Valid Accounts — credential misuse)",
    "credential_stuffing": "T1110.004 (Credential Stuffing)",
    "lateral_movement": "T1021 (Remote Services — Lateral Movement)",
    "device_spoofing": "T1036 (Masquerading)",
    "low_and_slow": "T1048 (Exfiltration Over Alternative Protocol)",
    "insider_drift": "T1078 (Valid Accounts — privilege expansion)",
}

# Attack type to integer label mapping (for XGBoost)
LABEL_TO_INT: dict[str, int] = {
    "normal": 0,
    "brute_force": 1,
    "impossible_travel": 2,
    "credential_stuffing": 3,
    "lateral_movement": 4,
    "device_spoofing": 5,
    "low_and_slow": 6,
    "insider_drift": 7,
}

INT_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_INT.items()}


# ---------- Sub-models ----------


class GeoLocation(BaseModel):
    """Geographic coordinates with city/country metadata."""

    city: str
    country: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DeviceFingerprint(BaseModel):
    """Device identification fields for spoofing detection."""

    os: str
    firmware_version: str
    mac_address: str
    protocol: str


# ---------- Main event schema ----------


class AccessEvent(BaseModel):
    """A single access/connection event in the access log.

    This is the atomic unit of data flowing through the entire pipeline.
    The `label` field is ONLY present in hidden_labels.csv for evaluation —
    it is NEVER fed to the detection pipeline at inference.
    """

    event_id: str
    entity_id: str
    entity_type: EntityType
    timestamp: datetime
    source_ip: str
    geo_location: GeoLocation
    resource_accessed: str
    auth_method: AuthMethod
    auth_success: bool
    session_duration: float = Field(ge=0, description="Duration in seconds")
    command_sequence: list[str] = Field(default_factory=list)
    device_fingerprint: DeviceFingerprint
    bytes_transferred: int = Field(ge=0, default=0)

    @field_validator("source_ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """Basic IPv4 format check."""
        parts = v.split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid IPv4 format: {v}")
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                raise ValueError(f"Invalid IPv4 octet: {part}")
        return v


class HiddenLabel(BaseModel):
    """Ground truth label — stored separately, joined only by event_id.

    Never enters the feature/detection pipeline.
    """

    event_id: str
    label: AnomalyLabel


# ---------- Entity profile schema ----------


class EntityProfile(BaseModel):
    """Per-entity behavioral fingerprint used to generate realistic synthetic data.

    Each entity has persistent behavioral characteristics that define their 'normal'.
    """

    entity_id: str
    entity_type: EntityType
    home_lat: float = Field(ge=-90, le=90)
    home_lon: float = Field(ge=-180, le=180)
    secondary_lat: float | None = None
    secondary_lon: float | None = None
    typical_hour_mean: float = Field(ge=0, le=24, description="Von Mises center (hours)")
    typical_hour_std: float = Field(gt=0, le=6, description="Von Mises concentration proxy")
    resource_set: list[str] = Field(min_length=3, max_length=20)
    session_duration_mean_log: float = Field(
        description="Mean of log-normal session duration (log-seconds)"
    )
    session_duration_std_log: float = Field(
        gt=0, default=0.4, description="Std of log-normal session duration"
    )
    auth_method: AuthMethod
    device_os: str
    device_firmware: str
    device_mac: str
    device_protocol: str
    avg_daily_events: float = Field(gt=0, default=8.0)
    bytes_mean: int = Field(ge=0, default=5000)
    bytes_std: int = Field(ge=0, default=2000)
    typical_commands: list[str] = Field(default_factory=list)
