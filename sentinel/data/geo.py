"""Geographic utilities — city database, haversine distance, coordinate helpers.

The city database provides realistic geo-locations for entity profiles and
attack injection (impossible travel needs real coordinates that are far apart).
"""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt

import numpy as np


# ---------- City database (50 cities with real lat/lon) ----------

CITY_DATABASE: list[dict[str, str | float]] = [
    # North America
    {"city": "New York", "country": "US", "lat": 40.7128, "lon": -74.0060},
    {"city": "Los Angeles", "country": "US", "lat": 34.0522, "lon": -118.2437},
    {"city": "Chicago", "country": "US", "lat": 41.8781, "lon": -87.6298},
    {"city": "Houston", "country": "US", "lat": 29.7604, "lon": -95.3698},
    {"city": "Toronto", "country": "CA", "lat": 43.6532, "lon": -79.3832},
    {"city": "Mexico City", "country": "MX", "lat": 19.4326, "lon": -99.1332},
    {"city": "San Francisco", "country": "US", "lat": 37.7749, "lon": -122.4194},
    {"city": "Seattle", "country": "US", "lat": 47.6062, "lon": -122.3321},
    # Europe
    {"city": "London", "country": "GB", "lat": 51.5074, "lon": -0.1278},
    {"city": "Paris", "country": "FR", "lat": 48.8566, "lon": 2.3522},
    {"city": "Berlin", "country": "DE", "lat": 52.5200, "lon": 13.4050},
    {"city": "Amsterdam", "country": "NL", "lat": 52.3676, "lon": 4.9041},
    {"city": "Madrid", "country": "ES", "lat": 40.4168, "lon": -3.7038},
    {"city": "Rome", "country": "IT", "lat": 41.9028, "lon": 12.4964},
    {"city": "Stockholm", "country": "SE", "lat": 59.3293, "lon": 18.0686},
    {"city": "Zurich", "country": "CH", "lat": 47.3769, "lon": 8.5417},
    # Asia
    {"city": "Mumbai", "country": "IN", "lat": 19.0760, "lon": 72.8777},
    {"city": "Delhi", "country": "IN", "lat": 28.7041, "lon": 77.1025},
    {"city": "Bangalore", "country": "IN", "lat": 12.9716, "lon": 77.5946},
    {"city": "Tokyo", "country": "JP", "lat": 35.6762, "lon": 139.6503},
    {"city": "Singapore", "country": "SG", "lat": 1.3521, "lon": 103.8198},
    {"city": "Shanghai", "country": "CN", "lat": 31.2304, "lon": 121.4737},
    {"city": "Beijing", "country": "CN", "lat": 39.9042, "lon": 116.4074},
    {"city": "Seoul", "country": "KR", "lat": 37.5665, "lon": 126.9780},
    {"city": "Dubai", "country": "AE", "lat": 25.2048, "lon": 55.2708},
    {"city": "Tel Aviv", "country": "IL", "lat": 32.0853, "lon": 34.7818},
    {"city": "Bangkok", "country": "TH", "lat": 13.7563, "lon": 100.5018},
    {"city": "Jakarta", "country": "ID", "lat": -6.2088, "lon": 106.8456},
    {"city": "Hyderabad", "country": "IN", "lat": 17.3850, "lon": 78.4867},
    {"city": "Chennai", "country": "IN", "lat": 13.0827, "lon": 80.2707},
    # South America
    {"city": "São Paulo", "country": "BR", "lat": -23.5505, "lon": -46.6333},
    {"city": "Buenos Aires", "country": "AR", "lat": -34.6037, "lon": -58.3816},
    {"city": "Bogota", "country": "CO", "lat": 4.7110, "lon": -74.0721},
    # Africa
    {"city": "Lagos", "country": "NG", "lat": 6.5244, "lon": 3.3792},
    {"city": "Cape Town", "country": "ZA", "lat": -33.9249, "lon": 18.4241},
    {"city": "Nairobi", "country": "KE", "lat": -1.2921, "lon": 36.8219},
    # Oceania
    {"city": "Sydney", "country": "AU", "lat": -33.8688, "lon": 151.2093},
    {"city": "Melbourne", "country": "AU", "lat": -37.8136, "lon": 144.9631},
    {"city": "Auckland", "country": "NZ", "lat": -36.8485, "lon": 174.7633},
    # Middle East / Central Asia
    {"city": "Istanbul", "country": "TR", "lat": 41.0082, "lon": 28.9784},
    {"city": "Riyadh", "country": "SA", "lat": 24.7136, "lon": 46.6753},
    # More US cities for density
    {"city": "Boston", "country": "US", "lat": 42.3601, "lon": -71.0589},
    {"city": "Atlanta", "country": "US", "lat": 33.7490, "lon": -84.3880},
    {"city": "Denver", "country": "US", "lat": 39.7392, "lon": -104.9903},
    {"city": "Miami", "country": "US", "lat": 25.7617, "lon": -80.1918},
    {"city": "Dallas", "country": "US", "lat": 32.7767, "lon": -96.7970},
    {"city": "Phoenix", "country": "US", "lat": 33.4484, "lon": -112.0740},
    {"city": "Portland", "country": "US", "lat": 45.5152, "lon": -122.6784},
    {"city": "Minneapolis", "country": "US", "lat": 44.9778, "lon": -93.2650},
    {"city": "Washington DC", "country": "US", "lat": 38.9072, "lon": -77.0369},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth (km).

    Uses the Haversine formula with Earth radius = 6371 km.

    Args:
        lat1: Latitude of point 1 (degrees).
        lon1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lon2: Longitude of point 2 (degrees).

    Returns:
        Distance in kilometers.
    """
    r = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def geo_velocity_kmh(
    lat1: float,
    lon1: float,
    ts1_epoch: float,
    lat2: float,
    lon2: float,
    ts2_epoch: float,
) -> float:
    """Calculate travel velocity between two geo-located events.

    Args:
        lat1, lon1: Coordinates of first event.
        ts1_epoch: Timestamp of first event (Unix epoch seconds).
        lat2, lon2: Coordinates of second event.
        ts2_epoch: Timestamp of second event (Unix epoch seconds).

    Returns:
        Velocity in km/h. Returns 0.0 if timestamps are identical.
    """
    dist = haversine_km(lat1, lon1, lat2, lon2)
    hours = abs(ts2_epoch - ts1_epoch) / 3600.0
    if hours <= 0:
        return float("inf") if dist > 0 else 0.0
    return dist / hours


def add_geo_noise(
    lat: float, lon: float, std_deg: float = 0.05, rng: np.random.Generator | None = None
) -> tuple[float, float]:
    """Add Gaussian noise to coordinates (simulates GPS/IP geolocation jitter).

    Args:
        lat: Base latitude.
        lon: Base longitude.
        std_deg: Standard deviation of noise in degrees (~5.5 km per 0.05 deg).
        rng: NumPy random generator for reproducibility.

    Returns:
        Tuple of (noisy_lat, noisy_lon), clamped to valid ranges.
    """
    if rng is None:
        rng = np.random.default_rng()
    noisy_lat = float(np.clip(lat + rng.normal(0, std_deg), -90, 90))
    noisy_lon = float(np.clip(lon + rng.normal(0, std_deg), -180, 180))
    return noisy_lat, noisy_lon


def get_distant_city(
    home_lat: float, home_lon: float, min_distance_km: float = 2000
) -> dict[str, str | float]:
    """Find a city that is at least `min_distance_km` away from the home location.

    Used for impossible travel attack injection — need genuinely distant locations.

    Args:
        home_lat: Entity's home latitude.
        home_lon: Entity's home longitude.
        min_distance_km: Minimum distance threshold.

    Returns:
        A city dict from CITY_DATABASE that is far enough away.
    """
    candidates = [
        c
        for c in CITY_DATABASE
        if haversine_km(home_lat, home_lon, c["lat"], c["lon"]) >= min_distance_km
    ]
    if not candidates:
        # Fallback: return the farthest city
        candidates = sorted(
            CITY_DATABASE,
            key=lambda c: haversine_km(home_lat, home_lon, c["lat"], c["lon"]),
            reverse=True,
        )
    return candidates[0]
