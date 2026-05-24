"""Trip segmentation: bronze.maps_visits + silver.maps_home_locations → silver.maps_trips.

Algorithm (DATA_MODEL.md §Maps — home anchor + trip segmentation):
  1. For each visit, compute haversine distance to the active home anchor.
  2. Mark visits "away" when distance_km > home.radius_km.
  3. Group consecutive away-visits into trip clusters; break on (a) a visit
     inside the home radius, or (b) a >24h gap between consecutive aways.
  4. Per cluster: trip_start = min(started_at), trip_end = max(ended_at),
     destination = argmax(dwell_time, place_name), country parsed from
     place_address tail, km = sum(maps_path.distance_m) overlapping the
     window.

Re-runs are full rebuilds (TRUNCATE+INSERT) because late-arriving visits can
retroactively shift trip boundaries — a stream MV would lock in stale values.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable

from ..._shared.clickhouse import get_client, insert_rows


log = logging.getLogger(__name__)


GAP_BREAK_HOURS = 24


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlat = lat2r - lat1r
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _country_from_address(address: str) -> str:
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[-1] if parts else ""


def _km_in_window(paths: list[tuple[datetime, datetime, int]], start: datetime, end: datetime) -> int:
    total = 0
    for s, e, dist in paths:
        if e <= start or s >= end:
            continue
        total += dist
    return int(total / 1000)


def segment_trips() -> int:
    """Rebuild silver.maps_trips. Returns number of trips written."""

    client = get_client()

    homes = client.query(
        "SELECT valid_from, lat, lng, radius_km FROM silver.maps_home_locations FINAL "
        "ORDER BY valid_from"
    ).result_rows
    if not homes:
        log.warning("No home anchor in silver.maps_home_locations — skipping segmentation.")
        return 0

    # Find the home active at a given visit timestamp.
    def home_at(ts: datetime) -> tuple[float, float, float] | None:
        active = None
        ts_date = ts.date() if hasattr(ts, "date") else ts
        for valid_from, lat, lng, radius_km in homes:
            if hasattr(valid_from, "date"):
                vf = valid_from.date()
            else:
                vf = valid_from
            if vf <= ts_date:
                active = (lat, lng, radius_km)
        return active

    visits = client.query(
        "SELECT started_at, ended_at, place_name, place_address, lat, lng "
        "FROM bronze.maps_visits FINAL "
        "WHERE place_id != '' OR place_name != '' "
        "ORDER BY started_at"
    ).result_rows

    paths_rows = client.query(
        "SELECT started_at, ended_at, distance_m "
        "FROM bronze.maps_path FINAL "
        "ORDER BY started_at"
    ).result_rows
    paths = [(s, e, int(d or 0)) for s, e, d in paths_rows]

    # Flag away-status per visit.
    flagged: list[tuple[datetime, datetime, str, str, float, float, bool]] = []
    for started_at, ended_at, place_name, place_address, lat, lng in visits:
        anchor = home_at(started_at)
        if not anchor:
            continue
        home_lat, home_lng, radius_km = anchor
        away = _haversine_km(lat, lng, home_lat, home_lng) > radius_km
        flagged.append((started_at, ended_at, place_name, place_address, lat, lng, away))

    # Group consecutive aways with a 24h gap break.
    trips: list[dict] = []
    current: list = []
    for row in flagged:
        started_at, ended_at, *_rest, away = row
        if not away:
            if current:
                trips.append(_finalize(current, paths))
                current = []
            continue
        if current and (started_at - current[-1][1]) > timedelta(hours=GAP_BREAK_HOURS):
            trips.append(_finalize(current, paths))
            current = []
        current.append(row)
    if current:
        trips.append(_finalize(current, paths))

    if not trips:
        log.info("No trips detected.")

    # TRUNCATE+INSERT — small table, full rebuild is safer than upsert.
    client.command("TRUNCATE TABLE silver.maps_trips")
    if trips:
        insert_rows(
            "maps_trips",
            trips,
            database="silver",
            column_names=["started_at", "ended_at", "days", "destination", "destination_country", "km"],
        )
    log.info("silver.maps_trips rebuilt with %d trip(s)", len(trips))
    return len(trips)


def _finalize(cluster: list, paths: list[tuple[datetime, datetime, int]]) -> dict:
    """Reduce a list of (started_at, ended_at, place_name, place_address, lat, lng, away) → trip row."""

    starts = [c[0] for c in cluster]
    ends = [c[1] for c in cluster]
    dwell: Counter[str] = Counter()
    addresses: dict[str, str] = {}
    for started_at, ended_at, place_name, place_address, *_ in cluster:
        if not place_name:
            continue
        dwell[place_name] += int((ended_at - started_at).total_seconds())
        addresses[place_name] = place_address

    destination = dwell.most_common(1)[0][0] if dwell else (cluster[0][2] or "Unknown")
    destination_country = _country_from_address(addresses.get(destination, "") or "")

    start_d: date = min(starts).date()
    end_d: date = max(ends).date()
    days = max(1, (end_d - start_d).days + 1)
    km = _km_in_window(paths, min(starts), max(ends))

    return {
        "started_at": start_d,
        "ended_at": end_d,
        "days": days,
        "destination": destination,
        "destination_country": destination_country,
        "km": km,
    }
