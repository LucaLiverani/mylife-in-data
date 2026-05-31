"""Google Data Portability-driven assets: Maps + YouTube history.

Maps Timeline data is post-2024 on-device only for many users; the probe
script (scripts/probe_maps_data_portability.py) tells you whether the cloud
copy is still there. If it isn't, fall back to manual on-device exports via
scripts/import_maps_timeline_export.py.
"""

from __future__ import annotations

import tempfile
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


def _run_maps_activity_ingest(context, *, years_back: float, days_back: int) -> dict:
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.activity_parser import parse_archive_for_activity
    from ingestion.google.maps.insert import insert_activity

    creds = context.resources.google_auth_portability.get_credentials()
    client = DataPortabilityClient(creds)

    start_time, end_time = _maps_ingest_window(years_back=years_back, days_back=days_back)
    context.log.info("Maps activity DP window: %s → %s", start_time.isoformat(), end_time.isoformat())

    job_id = client.initiate_archive(
        MAPS_ACTIVITY_RESOURCES, start_time=start_time, end_time=end_time
    )
    job = client.wait_for_archive(job_id)

    with tempfile.TemporaryDirectory(prefix="maps-act-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        rows = parse_archive_for_activity(root)

    n = insert_activity(rows)
    context.log.info("Inserted %d activity rows into bronze.maps_activity", n)
    return {"activity_rows": n}


@asset(
    group_name="google",
    description="One-shot 1y backfill of Maps activity (search/view/directions).",
    deps=[maps_schema],
    required_resource_keys={"google_auth_portability"},
)
def maps_activity_initial_backfill(context) -> dict:
    return _run_maps_activity_ingest(context, years_back=1.0, days_back=0)


# NOTE: the daily incremental Maps ingest is no longer a standalone asset —
# it's folded into `maps_youtube_dp_daily` (defined below) so Maps + YouTube
# share a single Data Portability archive and don't collide on the per-client
# 24h cooldown. `_run_maps_activity_ingest` is still used by the backfill above.


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

    job_id = client.initiate_archive(MAPS_SAVED_PLACES_RESOURCES)
    try:
        job = client.wait_for_archive(job_id)
    except Exception as exc:
        # 24h rate-limit can hit; parse the existing job_id from the error.
        import re

        m = re.search(r"job ([a-f0-9-]{36})", str(exc))
        if not m:
            raise
        job = client.get_state(m.group(1))

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
    try:
        n = adjudicate_trips(limit=limit)
    except LLMConfigError as exc:
        context.log.warning("LLM not configured (%s) — skipping trip adjudication", exc)
        return {"enriched": 0, "skipped": True}
    context.log.info("Enriched %d trip(s) via LLM", n)
    return {"enriched": n}


# ── Jobs + schedules ───────────────────────────────────────────────────────
# The unified daily Maps+YouTube DP job is defined at the end of this module
# (after both schemas + enrichment assets exist).
maps_private_places_job = define_asset_job(
    "maps_private_places_job",
    selection=AssetSelection.assets(maps_private_places_sync),
)


# Trip pipeline (segment → LLM-adjudicate), runnable on demand. Full wiring
# into the daily flow happens AFTER the dbt build (Phase 6) — the LLM step
# reads dbt-built silver views, so it must run post-build, not on this job's
# own schedule. No schedule attached here on purpose.
maps_trips_job = define_asset_job(
    "maps_trips_job",
    selection=AssetSelection.assets(maps_trip_segmentation, maps_trip_llm),
)


maps_private_places_schedule = ScheduleDefinition(
    job=maps_private_places_job,
    cron_schedule="0 5 * * 1",  # Monday 05:00 — saved places change slowly
    name="maps_private_places_schedule",
    description="Weekly refresh of the private-places spatial filter from starred places.",
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


def _youtube_ingest(context, *, years_back: float, days_back: int) -> dict:
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.youtube.parser import parse_archive
    from ingestion.google.youtube.insert import insert_watch_history, insert_search_history

    creds = context.resources.google_auth_portability.get_credentials()
    client = DataPortabilityClient(creds)

    start_time, end_time = _maps_ingest_window(years_back=years_back, days_back=days_back)
    context.log.info("YouTube DP window: %s → %s", start_time.isoformat(), end_time.isoformat())

    job_id = client.initiate_archive(YOUTUBE_RESOURCES, start_time=start_time, end_time=end_time)
    job = client.wait_for_archive(job_id)

    with tempfile.TemporaryDirectory(prefix="yt-dp-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        watch, search = parse_archive(root)

    n_watch = insert_watch_history(watch)
    n_search = insert_search_history(search)
    context.log.info("Inserted %d watch + %d search rows", n_watch, n_search)
    return {"watch": n_watch, "search": n_search}


@asset(
    group_name="google",
    description="One-shot 1y YouTube history backfill.",
    deps=[youtube_schema],
    required_resource_keys={"google_auth_portability"},
)
def youtube_history_initial_backfill(context) -> dict:
    return _youtube_ingest(context, years_back=1.0, days_back=0)


# NOTE: the daily incremental YouTube ingest is folded into
# `maps_youtube_dp_daily` (below). `_youtube_ingest` is still used by the
# one-shot backfill above.


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
def _run_combined_dp_ingest(context, *, years_back: float, days_back: int) -> dict:
    """One Data Portability archive covering BOTH myactivity.maps and
    myactivity.youtube. Google's DP cooldown is per OAuth client (~24h), so a
    single combined initiation is the only way to refresh both sources daily
    without the second hitting 429. The unpacked archive matches Takeout's
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

    job_id = client.initiate_archive(resources, start_time=start_time, end_time=end_time)
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
    return _run_combined_dp_ingest(context, years_back=0, days_back=1)


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
    cron_schedule="0 4 * * *",
    name="google_dp_daily_schedule",
    description="Daily 04:00 combined Maps + YouTube DP ingest + enrichment.",
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
