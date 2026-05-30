"""Trip segmentation from silver_geo_daily → silver.maps_trips.

Continuous GPS Timeline no longer exists, so trips are inferred from the daily
location timeline (silver_geo_daily): runs of consecutive away-days, tolerant
of short gaps (days with no Maps activity), bounded by a confirmed day back
home. Each away-day already required a directions signal upstream, so segments
reflect real movement, not searches.

Re-runs are full rebuilds (TRUNCATE+INSERT) — late-arriving activity can shift
trip boundaries, and the table stays tiny at personal-history scale.

This produces trip CANDIDATES (including short/uncertain ones). Phase 5 (LLM
adjudication) decides which are genuine trips vs. layovers / mis-geocodes and
names them.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import date

from ..._shared.clickhouse import get_client, insert_rows


log = logging.getLogger(__name__)

# Tolerate up to this many no-data days inside a trip before splitting it.
# (A trip you didn't open Maps on for a couple of days is still one trip.)
GAP_DAYS = 3


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def segment_trips() -> int:
    """Rebuild silver.maps_trips from silver_geo_daily. Returns trips written."""
    client = get_client()

    rows = client.query(
        "SELECT event_date, locality, country, lat, lng, km_from_home, away "
        "FROM silver.silver_geo_daily ORDER BY event_date"
    ).result_rows

    client.command("TRUNCATE TABLE silver.maps_trips")
    if not rows:
        log.info("silver_geo_daily empty — no trips.")
        return 0

    hb = client.query("SELECT home_lat, home_lng FROM silver.silver_home_base").result_rows
    home_lat, home_lng = (float(hb[0][0]), float(hb[0][1])) if hb else (0.0, 0.0)

    # Keep only away-days, then split into trips on gaps longer than GAP_DAYS.
    # Splitting on away-day gaps (not on home-days) means an isolated home day
    # mid-trip is smoothed over, while a genuine multi-day return home still
    # splits (the gap to the next away-day exceeds the tolerance).
    away_days = [
        (r[0], r[1], r[2], float(r[3]), float(r[4]), float(r[5]))
        for r in rows if r[6] == 1
    ]
    segments: list[list] = []
    current: list = []
    last_date: date | None = None
    for tup in away_days:
        if current and last_date is not None and (tup[0] - last_date).days > GAP_DAYS + 1:
            segments.append(current)
            current = []
        current.append(tup)
        last_date = tup[0]
    if current:
        segments.append(current)

    trips = [_finalize(seg, home_lat, home_lng) for seg in segments]
    trips = [t for t in trips if t["destination"]]

    if trips:
        insert_rows(
            "maps_trips",
            trips,
            database="silver",
            column_names=[
                "started_at", "ended_at", "days", "destination", "destination_country",
                "km", "localities", "countries", "max_km",
            ],
        )
    log.info("silver.maps_trips rebuilt with %d trip(s)", len(trips))
    return len(trips)


def _finalize(seg: list, home_lat: float, home_lng: float) -> dict:
    """Reduce a run of away-days → one trip row."""
    dates = [s[0] for s in seg]
    start_d, end_d = min(dates), max(dates)
    days = (end_d - start_d).days + 1

    # Destination = the locality with the most away-days in the window.
    loc_counts = Counter(s[1] for s in seg if s[1])
    destination = loc_counts.most_common(1)[0][0] if loc_counts else (seg[0][1] or "")
    destination_country = next((s[2] for s in seg if s[1] == destination and s[2]), "")

    localities = len({s[1] for s in seg if s[1]})
    countries = len({s[2] for s in seg if s[2]})
    max_km = int(max((s[5] for s in seg), default=0))

    # Distance estimate (great-circle): home → each daily centroid in order → home.
    pts = [(s[3], s[4]) for s in seg if s[3] and s[4]]
    km = 0.0
    if pts:
        km += _haversine_km(home_lat, home_lng, pts[0][0], pts[0][1])
        for i in range(len(pts) - 1):
            km += _haversine_km(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        km += _haversine_km(pts[-1][0], pts[-1][1], home_lat, home_lng)

    return {
        "started_at": start_d,
        "ended_at": end_d,
        "days": days,
        "destination": destination,
        "destination_country": destination_country,
        "km": int(km),
        "localities": localities,
        "countries": countries,
        "max_km": max_km,
    }
