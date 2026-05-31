"""Historical weather per trip from Open-Meteo → silver.maps_trip_weather.

For each trip in silver.maps_trips, find the destination's representative
coordinates (the directions-weighted centroid of the dominant locality's
in-window activity), fetch daily historical weather from Open-Meteo's free
archive API (no key required) over the trip window, and reduce it to a few
headline numbers + a short summary string.

Monotonic + resumable: trips already in silver.maps_trip_weather are skipped,
and each row is written as it's fetched. The archive API lags real time by
~5 days, so a very recent trip simply returns no data and is retried on a
later run (nothing is written until data exists).
"""

from __future__ import annotations

import logging
import time
from datetime import date

import requests

from ..._shared.clickhouse import get_client, insert_rows


log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

_WEATHER_COLUMNS = [
    "trip_key", "lat", "lng", "temp_mean", "temp_max", "temp_min",
    "precip_mm", "summary",
]


def _trip_key(start: date, end: date) -> str:
    return f"{start.isoformat()}_{end.isoformat()}"


def _destination_coords(client, destination: str, start: date, end: date) -> tuple[float, float] | None:
    """Representative coords for the trip: the dominant-locality activity
    centroid, falling back to the whole window's centroid."""
    s, e = start.isoformat(), end.isoformat()
    base = (
        "SELECT avg(lat), avg(lng), count() "
        "FROM silver.silver_maps_activity_enriched "
        "WHERE event_date >= %(s)s AND event_date <= %(e)s "
        "AND is_private = 0 AND match_confidence >= 0.4 AND lat != 0 AND lng != 0"
    )
    if destination:
        rows = client.query(
            base + " AND locality = %(loc)s",
            parameters={"s": s, "e": e, "loc": destination},
        ).result_rows
        if rows and rows[0][2]:
            return float(rows[0][0]), float(rows[0][1])
    rows = client.query(base, parameters={"s": s, "e": e}).result_rows
    if rows and rows[0][2]:
        return float(rows[0][0]), float(rows[0][1])
    return None


def _fetch_weather(lat: float, lng: float, start: date, end: date) -> dict | None:
    """Open-Meteo archive → aggregated window weather, or None if no data."""
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lng, 4),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
    }
    daily = _get(params)
    if not daily:
        return None

    def _avg(key: str) -> float | None:
        vals = [v for v in (daily.get(key) or []) if v is not None]
        return sum(vals) / len(vals) if vals else None

    temp_mean = _avg("temperature_2m_mean")
    if temp_mean is None:  # archive has the days but no temps → unusable
        return None
    temp_max = _avg("temperature_2m_max")
    temp_min = _avg("temperature_2m_min")
    precip = sum(v for v in (daily.get("precipitation_sum") or []) if v is not None)

    return {
        "lat": float(lat),
        "lng": float(lng),
        "temp_mean": round(temp_mean, 1),
        "temp_max": round(temp_max, 1) if temp_max is not None else round(temp_mean, 1),
        "temp_min": round(temp_min, 1) if temp_min is not None else round(temp_mean, 1),
        "precip_mm": round(precip, 1),
        "summary": f"{round(temp_mean)}°C avg · {round(precip)}mm rain",
    }


def _get(params: dict) -> dict | None:
    """GET the archive endpoint with retry/backoff; return the `daily` block."""
    session = _get.session  # type: ignore[attr-defined]
    for attempt in range(3):
        try:
            resp = session.get(ARCHIVE_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            log.warning("Open-Meteo HTTP error (attempt %d): %s", attempt + 1, exc)
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            log.warning("Open-Meteo HTTP %d (attempt %d) — backing off", resp.status_code, attempt + 1)
            time.sleep(2 + attempt * 2)
            continue
        if not resp.ok:
            # 400 for an out-of-range (too-recent) date window is expected — skip.
            log.info("Open-Meteo HTTP %d: %s", resp.status_code, resp.text[:160])
            return None
        return (resp.json() or {}).get("daily")
    return None


_get.session = requests.Session()  # type: ignore[attr-defined]


def fetch_trip_weather(limit: int | None = None) -> int:
    """Fetch weather for every not-yet-weathered trip. Returns rows written."""
    client = get_client()

    trips = client.query(
        "SELECT started_at, ended_at, destination FROM silver.maps_trips ORDER BY started_at"
    ).result_rows
    if not trips:
        log.info("silver.maps_trips empty — no weather to fetch.")
        return 0

    done = {
        r[0] for r in client.query(
            "SELECT trip_key FROM silver.maps_trip_weather FINAL"
        ).result_rows
    }

    written = 0
    for started_at, ended_at, destination in trips:
        key = _trip_key(started_at, ended_at)
        if key in done:
            continue
        if limit is not None and written >= limit:
            break
        try:
            coords = _destination_coords(client, destination or "", started_at, ended_at)
            if coords is None:
                log.info("trip %s: no coords for weather — skipping", key)
                continue
            wx = _fetch_weather(coords[0], coords[1], started_at, ended_at)
            if wx is None:
                log.info("trip %s: no archive weather yet — will retry", key)
                continue
        except Exception as exc:
            log.warning("trip %s weather failed: %s", key, exc)
            continue
        insert_rows(
            "maps_trip_weather", [{"trip_key": key, **wx}],
            database="silver", column_names=_WEATHER_COLUMNS,
        )
        written += 1
        log.info("weathered trip %s → %s", key, wx["summary"])

    log.info("Trip weather: %d trip(s) fetched", written)
    return written
