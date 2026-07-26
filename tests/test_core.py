"""Test suite for SentinelFlow."""

import pytest
import pandas as pd
from datetime import datetime
import numpy as np

from sentinel.schemas import AccessEvent, GeoLocation, DeviceFingerprint
from sentinel.features.profiles import EntityProfileStore
from sentinel.drift.monitor import DriftMonitor

def test_access_event_schema():
    """Test Pydantic validation."""
    event = AccessEvent(
        event_id="e1",
        entity_id="u1",
        entity_type="user",
        timestamp=datetime.now(),
        source_ip="192.168.1.1",
        geo_location=GeoLocation(city="NY", country="US", lat=40.7, lon=-74.0),
        resource_accessed="https://auth.corp/login",
        auth_method="password",
        auth_success=True,
        session_duration=120.5,
        device_fingerprint=DeviceFingerprint(os="Windows 11", firmware_version="1.0", mac_address="00:00:00", protocol="HTTPS")
    )
    assert event.source_ip == "192.168.1.1"

def test_invalid_ip_raises_error():
    """Test IP validation fails correctly."""
    with pytest.raises(ValueError):
        AccessEvent(
            event_id="e1",
            entity_id="u1",
            entity_type="user",
            timestamp=datetime.now(),
            source_ip="999.999.999.999",  # Invalid
            geo_location=GeoLocation(city="NY", country="US", lat=40.7, lon=-74.0),
            resource_accessed="https://auth.corp/login",
            auth_method="password",
            auth_success=True,
            session_duration=120.5,
            device_fingerprint=DeviceFingerprint(os="Windows", firmware_version="1", mac_address="00", protocol="HTTP")
        )

def test_profile_store_cold_start():
    """Test EWMA profile store cold start logic."""
    store = EntityProfileStore(min_events_for_full_trust=10)
    assert store.get_maturity_weight("new_user") == 0.0
    
    # Simulate 5 events
    for _ in range(5):
        store.score_and_update("new_user", "user", {"bytes": 1000})
        
    assert store.get_maturity_weight("new_user") == 0.5
    assert store.is_cold_start("new_user") is False  # it reaches exactly 0.5 (weight < 0.5 is cold start)

def test_adwin_drift_monitor():
    """Test ADWIN drift monitor."""
    monitor = DriftMonitor(delta=0.99) # Very high delta for testing to force drift
    
    # Stream of 0s
    for _ in range(30):
        monitor.update("user", False)
        
    # Sudden stream of 1s
    drifted = False
    for _ in range(30):
        if monitor.update("user", True):
            drifted = True
            break
            
    assert drifted, "Drift monitor should detect the shift"
