"""
Resolves a free-text birth place ("Greensboro, NC, USA") into lat/lon and the
correct UTC offset for that exact historical date (handles old DST rules).

Uses OpenStreetMap's free Nominatim geocoder (no API key needed, but please
keep request volume low / cache results -- see NOTE below for production use).
"""
import datetime
import requests
from timezonefinder import TimezoneFinder
import pytz

_tf = TimezoneFinder()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Small offline fallback so the app still works if the geocoding API is
# unreachable (e.g. sandboxed/firewalled environments during development,
# or a transient outage in production). Production deployments should rely
# on the live API for full city coverage; this is just a safety net.
_FALLBACK_CITIES = {
    "delhi": (28.6139, 77.2090, "Delhi, India"),
    "new delhi": (28.6139, 77.2090, "New Delhi, India"),
    "mumbai": (19.0760, 72.8777, "Mumbai, India"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru, India"),
    "bangalore": (12.9716, 77.5946, "Bengaluru, India"),
    "greensboro": (36.0726, -79.7920, "Greensboro, NC, USA"),
    "new york": (40.7128, -74.0060, "New York, NY, USA"),
    "london": (51.5074, -0.1278, "London, UK"),
}


def geocode_place(place_text):
    """Returns (lat, lon, display_name) or raises ValueError if not found."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": place_text, "format": "json", "limit": 1},
            headers={"User-Agent": "vedic-astrology-reading-app/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon, data[0].get("display_name", place_text)
    except requests.exceptions.RequestException:
        pass  # fall through to offline fallback below

    key = place_text.split(",")[0].strip().lower()
    if key in _FALLBACK_CITIES:
        return _FALLBACK_CITIES[key]

    raise ValueError(
        f"Could not find location: {place_text}. "
        "Try a more specific name, or enter latitude/longitude directly."
    )


def resolve_utc_offset(lat, lon, year, month, day, hour, minute):
    """
    Returns the UTC offset in hours (e.g. 5.5 for IST, -5.0 for EST) that was
    in effect at this lat/lon on this specific date -- correctly handling
    historical daylight saving rules.
    """
    tz_name = _tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        raise ValueError("Could not resolve timezone for this location")
    tz = pytz.timezone(tz_name)
    naive_dt = datetime.datetime(year, month, day, hour, minute)
    local_dt = tz.localize(naive_dt)
    offset = local_dt.utcoffset().total_seconds() / 3600.0
    return offset, tz_name


# NOTE for production:
# Nominatim's public endpoint has a 1 request/second rate limit and asks
# for a descriptive User-Agent (set above). For real traffic, switch to a
# paid geocoding API (Google, Mapbox, OpenCage) or self-host Nominatim,
# and cache place -> (lat, lon) lookups in a small database/dict so repeat
# city names don't hit the API every time.
