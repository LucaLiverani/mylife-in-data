"""Google Data Portability-driven assets: Maps + YouTube history.

Maps Timeline (location visits/paths) moved on-device for many users in 2024,
so the daily ingest uses MyActivity (search/view/directions) via Data
Portability instead. Full history is a one-time load from a manual Google
Takeout export (scripts/import_google_takeout.py).
"""

from __future__ import annotations

import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    RunRequest,
    ScheduleDefinition,
    SensorEvaluationContext,
    SkipReason,
    asset,
    define_asset_job,
    sensor,
)


REPO_ROOT_IN_CONTAINER = Path("/opt/dagster/repo")


def _ddl_path(filename: str) -> Path:
    p = REPO_ROOT_IN_CONTAINER / "warehouse" / "ddl" / filename
    if p.exists():
        return p
    return Path(__file__).resolve().parents[3] / "warehouse" / "ddl" / filename


# Data Portability resource names — short form, NOT the full scope URL.
# (scope URL  https://www.googleapis.com/auth/dataportability.myactivity.maps
#  → resource  myactivity.maps)
#
# Split into two groups because Google enforces different export semantics:
#   - myactivity.maps supports time-windowed exports (daily incremental works)
#   - maps.aliased_places + maps.starred_places are full-snapshot only
MAPS_ACTIVITY_RESOURCES = ["myactivity.maps"]
MAPS_SAVED_PLACES_RESOURCES = ["maps.aliased_places", "maps.starred_places"]


@asset(group_name="google", description="DDL bootstrap for Maps tables (Timeline + activity).")
def maps_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    # 50 = Timeline tables (legacy, filled by manual export only)
    # 51 = activity + place catalog + private filter (the primary daily flow)
    execute_file(str(_ddl_path("50_maps.sql")))
    execute_file(str(_ddl_path("51_maps_activity.sql")))
    return "ok"


def _maps_ingest_window(years_back: float = 0, days_back: int = 1) -> tuple[datetime, datetime]:
    end = datetime.now(tz=timezone.utc)
    if years_back > 0:
        return end - timedelta(days=int(years_back * 365)), end
    return end - timedelta(days=days_back), end


# NOTE: the daily incremental Maps ingest is folded into `maps_youtube_dp_daily`
# (defined below) so Maps + YouTube share a single Data Portability archive and
# don't collide on the per-client 24h cooldown.


@asset(
    group_name="google",
    description="Sync starred places (coords only) into silver.maps_private_places for spatial filtering.",
    deps=[maps_schema],
    required_resource_keys={"google_auth_portability"},
)
def maps_private_places_sync(context) -> int:
    """Pull starred places via DP (full snapshot — no time window), extract
    ONLY lat/lng (no names), and refresh silver.maps_private_places.

    The starred-places file contains friends' home addresses. Names never
    enter the warehouse — only coordinates, used as a spatial exclusion
    filter so those rows never reach gold tables."""
    from ingestion._shared.clickhouse import get_client
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.activity_parser import parse_starred_places_coords
    from ingestion.google.maps.insert import insert_private_places

    creds = context.resources.google_auth_portability.get_credentials()
    client = DataPortabilityClient(creds)

    # Shares the per-client 24h cooldown with the daily ingest. The week is
    # partitioned so this owns Mondays (see schedules below), but it can still
    # race the rolling boundary against Sunday's run — wait it out rather than
    # fail. Both initiate and wait happen before the TRUNCATE, so any failure
    # here leaves the existing private-places filter intact (fail-safe).
    job_id = _initiate_dp_with_cooldown_wait(context, client, MAPS_SAVED_PLACES_RESOURCES)
    job = client.wait_for_archive(job_id)

    with tempfile.TemporaryDirectory(prefix="maps-saved-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        coords = parse_starred_places_coords(root)

    # TRUNCATE + INSERT so removed stars drop from the filter on next sync.
    ch = get_client()
    ch.command("TRUNCATE TABLE silver.maps_private_places")
    n = insert_private_places(coords)
    context.log.info("Refreshed silver.maps_private_places: %d private coordinates", n)
    return n


@asset(
    group_name="google",
    description="Enrich unknown places in bronze.maps_activity via the configured geocoder → catalog.",
    deps=["maps_youtube_dp_daily"],  # combined Maps+YouTube DP ingest (defined below)
)
def maps_place_enrichment(context) -> dict:
    """Walk distinct place_ids / queries in bronze.maps_activity that aren't
    yet in bronze.maps_place_catalog. Each unknown place gets one Places API
    lookup (Find Place from Text, then Place Details) and is persisted.
    Catalog is monotonic — we never re-lookup."""
    import os

    from ingestion._shared.clickhouse import get_client
    from ingestion.google.maps.geocoder import (
        GeocoderConfigError,
        get_geocoder,
        get_or_lookup,
    )

    try:
        geocoder = get_geocoder()
    except GeocoderConfigError as exc:
        context.log.warning("Geocoder not configured (%s) — skipping place enrichment", exc)
        return {"looked_up": 0, "skipped": True}

    ch = get_client()
    # Build a worklist of unknown places keyed by `geo_key` — the URL ftid when
    # present, else a normalized-text key (`q:<text>`). Most activity rows have
    # NO ftid, so keying on geo_key (not `place_id != ''`) is what lets
    # searches / directions / place views enrich at all. geo_key + best_text
    # are defined once in the silver.maps_activity_keyed view so the lookup key
    # here matches the join key in silver_maps_activity_enriched exactly.
    # geo_key is the GROUP BY key, so select it raw. NB: alias the argMax to
    # `lookup_text`, NOT `best_text` — WHERE filters the raw `best_text` column,
    # and reusing that name for the aggregate makes ClickHouse bind the WHERE to
    # the aggregate → ILLEGAL_AGGREGATION. Per-run cap (override for backfill).
    limit = int(os.environ.get("MAPS_ENRICH_LIMIT", "200"))
    rows = ch.query(
        """
        SELECT
            geo_key,
            argMax(best_text, event_ts) AS lookup_text,
            avg(lat) AS lat,
            avg(lng) AS lng
        FROM silver.maps_activity_keyed
        WHERE geo_key != ''
          AND best_text != ''
          AND geo_key NOT IN (SELECT place_id FROM bronze.maps_place_catalog)
        GROUP BY geo_key
        LIMIT %(lim)s
        """,
        parameters={"lim": limit},
    ).result_rows

    looked_up = 0
    unresolved = 0
    failed = 0
    for geo_key, lookup_text, lat, lng in rows:
        text = lookup_text or ""
        try:
            result = get_or_lookup(
                place_id=geo_key,
                text=text,
                lat=float(lat or 0),
                lng=float(lng or 0),
                geocoder=geocoder,
                ch=ch,
            )
        except Exception as exc:
            context.log.warning("lookup failed for %s (%s): %s", geo_key, text, exc)
            failed += 1
            continue
        # get_or_lookup negative-caches junk/misses (an 'unresolved' sentinel
        # row) so they leave the worklist — result is None for those.
        if result is None:
            unresolved += 1
        else:
            looked_up += 1
    context.log.info(
        "Place enrichment via %s: resolved=%d, unresolved=%d, errors=%d (limit %d/run)",
        geocoder.provider, looked_up, unresolved, failed, limit,
    )
    return {"looked_up": looked_up, "unresolved": unresolved, "failed": failed}


@asset(
    group_name="google",
    description="Rebuild silver.maps_trips after each Timeline import (manual export-driven).",
    deps=[maps_schema],
)
def maps_trip_segmentation(context) -> int:
    from ingestion.google.maps.trip_segmentation import segment_trips

    n = segment_trips()
    context.log.info("Wrote %d trips to silver.maps_trips", n)
    return n


@asset(
    group_name="google",
    description="LLM adjudication of inferred trips → silver.maps_trips_enriched (verdict, type, de-noised destination, title, summary).",
    deps=[maps_trip_segmentation],
)
def maps_trip_llm(context) -> dict:
    """Name + classify + de-noise each trip candidate via the configured LLM.

    Reads silver.maps_trips (candidates) plus the window's Maps activity
    (silver_maps_activity_enriched) and Calendar corroboration
    (silver_calendar_geo), and writes one verdict row per trip to
    silver.maps_trips_enriched. Monotonic — only un-enriched trips are
    adjudicated, so a re-run is cheap. Skips gracefully when LLM_* is unset.

    Depends on dbt views (silver_maps_activity_enriched, silver_calendar_geo)
    being current, so in the daily flow this runs AFTER the dbt build."""
    import os

    from ingestion._shared.llm import LLMConfigError
    from ingestion.google.maps.trip_llm import adjudicate_trips

    raw_limit = os.environ.get("MAPS_TRIP_LLM_LIMIT")
    limit = int(raw_limit) if raw_limit else None
    # MAPS_TRIP_LLM_FORCE=1 re-adjudicates every trip (regeneration after a
    # prompt change); unset/0 keeps the cheap monotonic default.
    force = os.environ.get("MAPS_TRIP_LLM_FORCE", "").lower() in {"1", "true", "yes"}
    try:
        n = adjudicate_trips(limit=limit, force=force)
    except LLMConfigError as exc:
        context.log.warning("LLM not configured (%s) — skipping trip adjudication", exc)
        return {"enriched": 0, "skipped": True}
    context.log.info("Enriched %d trip(s) via LLM", n)
    return {"enriched": n}


@asset(
    group_name="google",
    description="Fetch historical weather per trip (Open-Meteo, no key) → silver.maps_trip_weather.",
    deps=[maps_trip_segmentation],
)
def maps_trip_weather(context) -> dict:
    """Weather for each trip's destination over its window. Monotonic — only
    un-weathered trips are fetched. Independent of the LLM step (keys on the
    geometric trip), so it can run alongside maps_trip_llm after segmentation."""
    from ingestion.google.maps.trip_weather import fetch_trip_weather

    n = fetch_trip_weather()
    context.log.info("Fetched weather for %d trip(s)", n)
    return {"weathered": n}


# ── Jobs + schedules ───────────────────────────────────────────────────────
# The unified daily Maps+YouTube DP job is defined at the end of this module
# (after both schemas + enrichment assets exist).
maps_private_places_job = define_asset_job(
    "maps_private_places_job",
    selection=AssetSelection.assets(maps_private_places_sync),
)


# Trip pipeline: segment → {LLM-adjudicate, fetch weather}. Runs AFTER the
# 09:00 dbt build, since segmentation/LLM read dbt-built silver views and gold
# (gold_maps_trips) is a live view over the silver tables these assets write —
# no second dbt build needed. maps_trip_llm + maps_trip_weather both depend on
# segmentation and run once it completes.
maps_trips_job = define_asset_job(
    "maps_trips_job",
    selection=AssetSelection.assets(maps_trip_segmentation, maps_trip_llm, maps_trip_weather),
)


maps_trips_schedule = ScheduleDefinition(
    job=maps_trips_job,
    cron_schedule="30 9 * * *",  # 09:30 UTC — after the 09:00 dbt build
    name="maps_trips_schedule",
    description="Daily 09:30 UTC — re-segment trips, then LLM-adjudicate + fetch weather.",
    default_status=DefaultScheduleStatus.RUNNING,
)


maps_private_places_schedule = ScheduleDefinition(
    job=maps_private_places_job,
    # Monday 04:00 — owns the shared per-client DP cooldown on Mondays (the
    # combined activity ingest skips Monday for this). Same 04:00 slot as the
    # other days, so the cooldown boundary stays at a single time of day.
    cron_schedule="0 4 * * 1",
    name="maps_private_places_schedule",
    description="Weekly (Monday 04:00 UTC) refresh of the private-places spatial filter from starred places.",
    default_status=DefaultScheduleStatus.RUNNING,
)


# ── YouTube ────────────────────────────────────────────────────────────────
# Watch + search history live under `myactivity.youtube` (a DP resource short
# name, NOT a scope URL). Scope-side, the OAuth grant uses the full URL
# https://www.googleapis.com/auth/dataportability.myactivity.youtube.
YOUTUBE_RESOURCES = [
    "myactivity.youtube",
]


@asset(group_name="google", description="DDL bootstrap for YouTube bronze tables.")
def youtube_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    execute_file(str(_ddl_path("60_youtube.sql")))
    return "ok"


# NOTE: the daily incremental YouTube ingest is folded into
# `maps_youtube_dp_daily` (below).


@asset(
    group_name="google",
    description="Enrich unknown YouTube videos + channels via Data API v3.",
    deps=["maps_youtube_dp_daily"],  # combined Maps+YouTube DP ingest (defined below)
    # Data API v3 uses youtube.readonly (a standard scope), NOT Data Portability.
    required_resource_keys={"google_auth_standard"},
)
def youtube_metadata_enricher(context) -> dict:
    from ingestion.google.youtube.enricher import enrich

    creds = context.resources.google_auth_standard.get_credentials()
    counts = enrich(creds)
    context.log.info("Enricher: %s", counts)
    return counts


# ── Unified daily Data Portability ingest (Maps + YouTube) ──────────────────
# Google's DP cooldown is per OAuth client (~24h), anchored to the *last*
# initiate, and allows only one initiate per ~24h. That shapes both the
# schedule and this helper:
#
#   - The week is PARTITIONED so exactly one DP initiate happens per day, all at
#     04:00 UTC: maps_private_places_sync owns Mondays (full-snapshot saved
#     places), the combined activity ingest owns the other six days (see the
#     crons below). This is why the daily cron excludes Monday — two initiates
#     in one 24h window would 429 the second, which used to silently starve the
#     weekly saved-places refresh.
#   - A daily job vs a 24h cooldown still lands on its own rolling boundary, so
#     anything that perturbs the anchor (a manual re-run, scheduler/container
#     lag) makes the next run briefly race it. Two guards absorb that:
#       1. DP_DAILY_LOOKBACK_DAYS > 1 — myactivity.* exports are time-windowed,
#          so a fully skipped day would be a permanent gap (the next run only
#          fetches its own window). bronze tables are ReplacingMergeTree on
#          natural keys, so overlapping windows dedup for free; over-fetching a
#          few days lets any single missed/late run (incl. the Monday skip)
#          self-heal on the next success.
#       2. _initiate_dp_with_cooldown_wait — on a time-based 429 the run sleeps
#          out the cooldown and retries (same-day recovery), capped at
#          DP_COOLDOWN_MAX_WAIT_S so a far-off cooldown (e.g. a midday backfill)
#          surfaces loudly and defers to guard #1 instead of blocking a worker.
DP_DAILY_LOOKBACK_DAYS = 3
DP_COOLDOWN_MAX_WAIT_S = 75 * 60
# Skew margin added when sleeping to the cooldown's clear time. Kept small: it's
# also the per-day "creep" the anchor gains each time we re-initiate just after
# the boundary, so a large buffer would slowly inflate the daily wait.
DP_COOLDOWN_BUFFER_S = 15


def _initiate_dp_with_cooldown_wait(
    context, client, resources, start_time=None, end_time=None
) -> str:
    """initiate_archive, tolerating Google's per-client 24h cooldown.

    On a time-based 429 we sleep until the cooldown clears (+skew buffer) and
    retry, so the *scheduled* run recovers the same day. Bounded by
    DP_COOLDOWN_MAX_WAIT_S — past that (or if the retry time is unparseable) we
    re-raise so the failure alerts and the next run's overlapping window
    backfills the gap. Shared by the daily combined ingest and the weekly
    saved-places sync (which passes no time window)."""
    from ingestion.google.portability import DataPortabilityRateLimited

    waited = 0.0
    while True:
        try:
            return client.initiate_archive(resources, start_time=start_time, end_time=end_time)
        except DataPortabilityRateLimited as exc:
            if exc.retry_after is None:
                context.log.error("DP cooldown 429 with no parseable retry time — giving up: %s", exc)
                raise
            # Sleep exactly to the clear time (+buffer); the 30s floor only kicks
            # in when the cooldown should already be clear but Google still 429s
            # (clock skew) — a brief retry rather than per-day creep.
            sleep_s = exc.seconds_until_ready(buffer_s=DP_COOLDOWN_BUFFER_S)
            if sleep_s <= 0:
                sleep_s = 30.0
            if waited + sleep_s > DP_COOLDOWN_MAX_WAIT_S:
                context.log.error(
                    "DP per-client cooldown until %s (prev jobs: %s) exceeds the %ds wait cap — "
                    "giving up; the next run's %dd window will backfill this gap.",
                    exc.retry_after.isoformat(), ",".join(exc.previous_job_ids) or "?",
                    DP_COOLDOWN_MAX_WAIT_S, DP_DAILY_LOOKBACK_DAYS,
                )
                raise
            context.log.warning(
                "DP per-client cooldown until %s — sleeping %.0fs then retrying initiate.",
                exc.retry_after.isoformat(), sleep_s,
            )
            time.sleep(sleep_s)
            waited += sleep_s


def _run_combined_dp_ingest(context, *, years_back: float, days_back: int) -> dict:
    """One Data Portability archive covering BOTH myactivity.maps and
    myactivity.youtube. Google's DP cooldown is per OAuth client (~24h), so a
    single combined initiation is the only way to refresh both sources daily
    without the second hitting 429 (the cron can still race the cooldown — see
    _initiate_dp_with_cooldown_wait). The unpacked archive matches Takeout's
    layout, so the maps + youtube parsers each select their own files."""
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.activity_parser import parse_archive_for_activity
    from ingestion.google.maps.insert import insert_activity
    from ingestion.google.youtube.parser import parse_archive
    from ingestion.google.youtube.insert import insert_watch_history, insert_search_history

    creds = context.resources.google_auth_portability.get_credentials()
    client = DataPortabilityClient(creds)

    start_time, end_time = _maps_ingest_window(years_back=years_back, days_back=days_back)
    resources = MAPS_ACTIVITY_RESOURCES + YOUTUBE_RESOURCES
    context.log.info(
        "Combined DP window %s → %s for %s",
        start_time.isoformat(), end_time.isoformat(), resources,
    )

    job_id = _initiate_dp_with_cooldown_wait(context, client, resources, start_time, end_time)
    job = client.wait_for_archive(job_id)

    with tempfile.TemporaryDirectory(prefix="dp-combined-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        activity_rows = parse_archive_for_activity(root)
        watch, search = parse_archive(root)

    n_activity = insert_activity(activity_rows)
    n_watch = insert_watch_history(watch)
    n_search = insert_search_history(search)
    context.log.info(
        "Combined DP ingest: maps=%d, yt_watch=%d, yt_search=%d", n_activity, n_watch, n_search
    )
    return {"activity_rows": n_activity, "watch": n_watch, "search": n_search}


@asset(
    group_name="google",
    description="Daily combined Maps + YouTube Data Portability ingest — one archive, avoids the per-client 24h-cooldown collision.",
    deps=[maps_schema, youtube_schema],
    required_resource_keys={"google_auth_portability"},
)
def maps_youtube_dp_daily(context) -> dict:
    return _run_combined_dp_ingest(context, years_back=0, days_back=DP_DAILY_LOOKBACK_DAYS)


# Single daily job: combined DP ingest → Maps place enrichment + YouTube
# metadata enrichment. Replaces the old colliding maps_daily (04:00) and
# youtube_daily (04:30) schedules.
google_dp_daily_job = define_asset_job(
    "google_dp_daily_job",
    selection=AssetSelection.assets(
        maps_youtube_dp_daily, maps_place_enrichment, youtube_metadata_enricher
    ),
)


google_dp_daily_schedule = ScheduleDefinition(
    job=google_dp_daily_job,
    # 04:00 UTC every day EXCEPT Monday (0=Sun … 6=Sat). Monday is reserved for
    # maps_private_places_sync, which shares the per-client 24h DP cooldown and
    # can't co-exist with a second initiate in the same window. The Monday gap
    # in activity is backfilled by Tuesday's DP_DAILY_LOOKBACK_DAYS window.
    cron_schedule="0 4 * * 0,2,3,4,5,6",
    name="google_dp_daily_schedule",
    description="Combined Maps + YouTube DP ingest + enrichment, 04:00 UTC Sun + Tue–Sat (Mon reserved for saved-places).",
    default_status=DefaultScheduleStatus.RUNNING,
)


youtube_enricher_job = define_asset_job(
    "youtube_enricher_job",
    selection=AssetSelection.assets(youtube_metadata_enricher),
)


@sensor(
    job=youtube_enricher_job,
    minimum_interval_seconds=600,
    name="youtube_metadata_enricher_sensor",
    description="Trigger enrichment when bronze has unknown video/channel IDs.",
    default_status=DefaultSensorStatus.RUNNING,
)
def youtube_metadata_enricher_sensor(context: SensorEvaluationContext):
    """Fire when bronze.youtube_watch_history has video_ids missing from bronze.youtube_videos."""
    from ingestion._shared.clickhouse import get_client

    try:
        client = get_client()
        n_videos = client.query(
            "SELECT count(DISTINCT video_id) FROM bronze.youtube_watch_history "
            "WHERE video_id != '' AND video_id NOT IN (SELECT video_id FROM bronze.youtube_videos)"
        ).result_rows[0][0]
        n_channels = client.query(
            "SELECT count(DISTINCT channel_id) FROM bronze.youtube_videos "
            "WHERE channel_id != '' AND channel_id NOT IN (SELECT channel_id FROM bronze.youtube_channels)"
        ).result_rows[0][0]
    except Exception as exc:
        return SkipReason(f"sensor check failed: {exc}")

    if (n_videos or 0) + (n_channels or 0) == 0:
        return SkipReason("no unknown YouTube IDs")
    return RunRequest(
        run_key=f"yt-enrich-v{n_videos}-c{n_channels}",
        tags={"missing_videos": str(n_videos), "missing_channels": str(n_channels)},
    )
