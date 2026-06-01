"""LLM adjudication of inferred trips → silver.maps_trips_enriched.

silver.maps_trips holds geometric trip CANDIDATES (runs of away-days derived
from Maps activity). This module gathers each candidate's window evidence — the
Maps activity that actually happened (top localities, countries, notable
places) plus any corroborating Calendar events (flights, hotels, foreign
all-day blocks from silver_calendar_geo) — and asks an LLM to:
  * decide whether it's a genuine trip (vs. a layover / mis-geocode / search-
    only artifact),
  * classify it (leisure / business / weekend / …),
  * pick ONE de-noised destination (ignoring one-off mis-geocoded outliers),
  * write a short title + summary,
  * flag a mega-trip that should be split into several.

Results land in silver.maps_trips_enriched keyed by `trip_key` ('<start>_<end>').
Monotonic + resumable: trips already enriched are skipped and each verdict is
written as soon as it returns, so an interrupted backfill resumes cleanly. At
personal-history scale (~15 trips) this is one cheap LLM call apiece.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from ..._shared.llm import LLMClient

# get_client / insert_rows are imported lazily inside adjudicate_trips so this
# module (and its prompt-building helpers) import cleanly without the ClickHouse
# driver present — handy for unit-testing the prompt off the warehouse.


log = logging.getLogger(__name__)

_TRIP_TYPES = {
    "leisure", "business", "weekend", "day_trip", "relocation", "visiting", "other",
}

_ENRICHED_COLUMNS = [
    "trip_key", "started_at", "ended_at", "days", "is_trip", "confidence",
    "trip_type", "title", "destination_label", "destination_country",
    "summary", "evidence", "suggested_split", "model",
]

# Calendar evidence reaches a couple of days past the geometric window so the
# outbound/return flight and a multi-day block that starts the day before are
# still caught.
_CAL_BUFFER_DAYS = 2


def _trip_key(start: date, end: date) -> str:
    return f"{start.isoformat()}_{end.isoformat()}"


def _clamp01(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def _s(v, limit: int) -> str:
    return str(v or "").strip()[:limit]


def _gather_activity(client, start: date, end: date) -> dict:
    """Aggregate the confident, non-private Maps activity inside the window."""
    s, e = start.isoformat(), end.isoformat()
    base = (
        "FROM silver.silver_maps_activity_enriched "
        "WHERE event_date >= %(s)s AND event_date <= %(e)s "
        "AND is_private = 0 AND match_confidence >= 0.4"
    )
    params = {"s": s, "e": e}

    totals = client.query(
        "SELECT count(), countIf(activity_type='directions'), "
        "countIf(activity_type='search'), uniqExact(country) "
        f"{base} AND locality != ''",
        parameters=params,
    ).result_rows
    n, n_dir, n_search, n_countries = (totals[0] if totals else (0, 0, 0, 0))

    localities = client.query(
        "SELECT locality, country, countIf(activity_type='directions') AS dir, count() AS n "
        f"{base} AND locality != '' "
        "GROUP BY locality, country ORDER BY dir DESC, n DESC LIMIT 10",
        parameters=params,
    ).result_rows

    places = client.query(
        "SELECT place_name, any(primary_type) AS t, count() AS n "
        f"{base} AND place_name != '' "
        "GROUP BY place_name ORDER BY n DESC LIMIT 12",
        parameters=params,
    ).result_rows

    return {
        "n": n, "n_dir": n_dir, "n_search": n_search, "n_countries": n_countries,
        "localities": localities, "places": places,
    }


def _gather_calendar(client, start: date, end: date) -> list:
    """Travel-relevant Calendar events overlapping the window (±buffer).

    Tolerant of silver_calendar_geo not existing yet (first deploy, before a
    dbt build) — returns [] so adjudication still runs on Maps evidence alone.
    """
    s = (start - timedelta(days=_CAL_BUFFER_DAYS)).isoformat()
    e = (end + timedelta(days=_CAL_BUFFER_DAYS)).isoformat()
    try:
        return client.query(
            "SELECT title, location, geo_locality, geo_country, "
            "toDate(started_at), toDate(ended_at), is_all_day, is_multi_day, "
            "is_travel_title, km_from_home "
            "FROM silver.silver_calendar_geo "
            "WHERE toDate(started_at) <= %(e)s AND toDate(ended_at) >= %(s)s "
            "AND (corroborates_travel = 1 OR is_multi_day = 1) "
            "ORDER BY started_at LIMIT 25",
            parameters={"s": s, "e": e},
        ).result_rows
    except Exception as exc:  # view missing / transient — Maps evidence still stands
        log.debug("calendar evidence unavailable for %s..%s: %s", s, e, exc)
        return []


def _format_evidence(trip, activity: dict, calendar: list) -> str:
    start, end, days, dest, dest_country, km, localities, countries, max_km = trip
    lines = [
        "CANDIDATE TRIP",
        f"dates: {start.isoformat()} → {end.isoformat()} ({days} days)",
        f"geometric destination guess: {dest or '?'}, {dest_country or '?'}",
        f"distinct localities: {localities}; distinct countries: {countries}; "
        f"farthest from home: {max_km} km; round-trip estimate: {km} km",
        "",
        "MAPS ACTIVITY IN WINDOW",
        f"totals: {activity['n']} activities "
        f"({activity['n_dir']} navigations, {activity['n_search']} searches) "
        f"across {activity['n_countries']} country/countries",
    ]
    if activity["localities"]:
        lines.append("top localities (by navigation):")
        for loc, country, dir_n, n in activity["localities"]:
            lines.append(f"  - {loc}, {country} — {dir_n} navigations, {n} activities")
    if activity["places"]:
        lines.append("notable places:")
        for name, ptype, n in activity["places"]:
            lines.append(f"  - {name}" + (f" ({ptype})" if ptype else "") + f" ×{n}")

    lines += ["", "CALENDAR EVENTS IN WINDOW"]
    if calendar:
        for (title, loc, geo_loc, geo_country, sdate, edate, all_day,
             multi_day, travel_title, km_home) in calendar:
            tags = []
            if all_day:
                tags.append("all-day")
            if multi_day:
                tags.append("multi-day")
            if travel_title:
                tags.append("travel-title")
            geo = ""
            if geo_loc or geo_country:
                geo = f" [geocoded: {geo_loc}, {geo_country}, {km_home}km from home]"
            loc_str = f" @ {loc}" if loc else ""
            tag_str = f" ({', '.join(tags)})" if tags else ""
            lines.append(f"  - {sdate.isoformat()} {title}{loc_str}{geo}{tag_str}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _build_messages(trip, home: dict, activity: dict, calendar: list) -> list:
    home_loc = home.get("locality") or "the home base"
    home_country = home.get("country") or ""
    system = (
        "You are a travel-history analyst. You are given evidence for a single "
        "candidate trip inferred from a person's Google Maps activity and Google "
        f"Calendar. The person's HOME BASE is {home_loc}, {home_country}; activity "
        "there is NOT travel.\n\n"
        "A GENUINE TRIP means the person was physically away from their home area "
        "(a city far from home, or a different country) for at least a day — for "
        "leisure, business, visiting people, etc. NOT a genuine trip: ordinary "
        "local days, a single mis-geocoded activity, or a window whose foreign/far "
        "signal came only from searches (trip PLANNING) rather than being there.\n\n"
        "DE-NOISE: pick ONE primary destination (the dominant place). Ignore "
        "one-off outliers — e.g. a single activity geocoded to a random far country "
        "inside an otherwise-Berlin trip is noise; it must not set the destination "
        "or inflate the trip. If the window clearly contains MULTIPLE distinct trips "
        "separated by a return home (e.g. two far-apart countries weeks apart), "
        "populate suggested_split.\n\n"
        "CALENDAR: 'Holidays in <country>' entries are public-holiday calendar "
        "subscriptions, NOT evidence of being there. Weigh flights, hotels, and "
        "foreign/far event locations far more.\n\n"
        "AUDIENCE: 'title' and 'summary' are shown to the traveler as a keepsake "
        "recap of the trip, so write them about the trip itself — never about how "
        "you reached your verdict. Your reasoning goes in 'evidence', which is "
        "internal and never shown.\n\n"
        "Respond with ONLY a JSON object (no prose, no code fence) with EXACTLY "
        "these keys:\n"
        '{\n'
        '  "is_trip": boolean,\n'
        '  "confidence": number between 0 and 1,\n'
        '  "trip_type": one of "leisure","business","weekend","day_trip","relocation","visiting","other",\n'
        '  "destination_label": string (clean city or region; "" if not a trip),\n'
        '  "destination_country": string (country name; "" if unknown),\n'
        '  "title": string (short, e.g. "Long weekend in Berlin"; "" if not a trip),\n'
        '  "summary": string — 1-2 sentences recapping the trip for the traveler: where they went and what the visit was like (notable places, neighbourhoods, the overall feel). Describe the trip itself, not why it qualifies as a trip; "" if not a trip,\n'
        '  "evidence": string — one short sentence naming the key signals you relied on (your internal rationale; keep all "why I decided this" wording OUT of summary),\n'
        '  "suggested_split": array of {"start":"YYYY-MM-DD","end":"YYYY-MM-DD","label":string} — [] unless clearly multiple trips\n'
        '}'
    )
    user = _format_evidence(trip, activity, calendar)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _to_row(trip_key: str, trip, obj: dict, model: str) -> dict:
    start, end, days = trip[0], trip[1], trip[2]
    trip_type = _s(obj.get("trip_type"), 32).lower().replace("-", "_").replace(" ", "_")
    if trip_type not in _TRIP_TYPES:
        trip_type = "other"
    split = obj.get("suggested_split")
    split_str = ""
    if isinstance(split, list) and split:
        split_str = json.dumps(split, ensure_ascii=False)[:2000]
    return {
        "trip_key": trip_key,
        "started_at": start,
        "ended_at": end,
        "days": int(days),
        "is_trip": 1 if obj.get("is_trip") else 0,
        "confidence": _clamp01(obj.get("confidence")),
        "trip_type": trip_type,
        "title": _s(obj.get("title"), 200),
        "destination_label": _s(obj.get("destination_label"), 200),
        "destination_country": _s(obj.get("destination_country"), 100),
        "summary": _s(obj.get("summary"), 1000),
        "evidence": _s(obj.get("evidence"), 500),
        "suggested_split": split_str,
        "model": model[:64],
    }


def adjudicate_trips(limit: int | None = None, force: bool = False) -> int:
    """Adjudicate every not-yet-enriched trip in silver.maps_trips.

    With force=True, re-adjudicate ALL trips even if already enriched — used to
    regenerate verdicts/summaries after a prompt change. Returns the number of
    trips enriched this run. Raises LLMConfigError (from LLMClient) when the
    LLM_* env is unset — callers (the Dagster asset) catch it and skip
    gracefully.
    """
    from ..._shared.clickhouse import get_client, insert_rows

    client = get_client()
    llm = LLMClient()

    home_rows = client.query(
        "SELECT home_locality, home_country FROM silver.silver_home_base"
    ).result_rows
    home = (
        {"locality": home_rows[0][0], "country": home_rows[0][1]}
        if home_rows else {"locality": "", "country": ""}
    )

    trips = client.query(
        "SELECT started_at, ended_at, days, destination, destination_country, "
        "km, localities, countries, max_km FROM silver.maps_trips ORDER BY started_at"
    ).result_rows
    if not trips:
        log.info("silver.maps_trips empty — nothing to adjudicate.")
        return 0

    # force re-runs every trip (regeneration after a prompt change); the table
    # is ReplacingMergeTree(_enriched_at) read with FINAL, so the fresh rows —
    # carrying a later _enriched_at — supersede the old verdicts with no
    # destructive truncate and no window where the dashboard loses enrichment.
    done = set() if force else {
        r[0] for r in client.query(
            "SELECT trip_key FROM silver.maps_trips_enriched FINAL"
        ).result_rows
    }

    enriched = 0
    for trip in trips:
        key = _trip_key(trip[0], trip[1])
        if key in done:
            continue
        if limit is not None and enriched >= limit:
            break
        try:
            activity = _gather_activity(client, trip[0], trip[1])
            calendar = _gather_calendar(client, trip[0], trip[1])
            messages = _build_messages(trip, home, activity, calendar)
            obj = llm.chat_json(messages, max_completion_tokens=4096)
            row = _to_row(key, trip, obj, llm.model)
        except Exception as exc:
            log.warning("trip %s adjudication failed: %s", key, exc)
            continue
        # Write each verdict immediately so an interrupted run stays resumable.
        insert_rows("maps_trips_enriched", [row], database="silver", column_names=_ENRICHED_COLUMNS)
        enriched += 1
        log.info("enriched trip %s → is_trip=%s '%s'", key, row["is_trip"], row["title"])

    log.info("LLM trip adjudication: %d trip(s) enriched", enriched)
    return enriched
