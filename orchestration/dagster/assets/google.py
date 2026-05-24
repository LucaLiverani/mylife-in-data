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


# Maps DP resource scopes — keep in sync with scopes requested by the OAuth
# flow (dashboard/functions/_shared/google-auth.ts).
MAPS_RESOURCES = [
    "https://www.googleapis.com/auth/dataportability.maps.aliased_places",
    "https://www.googleapis.com/auth/dataportability.maps.starred_places",
]


@asset(group_name="google", description="DDL bootstrap for Maps bronze + silver tables.")
def maps_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    execute_file(str(_ddl_path("50_maps.sql")))
    return "ok"


def _maps_ingest_window(years_back: float = 0, days_back: int = 1) -> tuple[datetime, datetime]:
    end = datetime.now(tz=timezone.utc)
    if years_back > 0:
        return end - timedelta(days=int(years_back * 365)), end
    return end - timedelta(days=days_back), end


def _run_maps_archive(context, *, years_back: float, days_back: int) -> dict:
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.parser import parse_archive
    from ingestion.google.maps.insert import insert_visits, insert_paths

    creds = context.resources.google_auth.get_credentials()
    client = DataPortabilityClient(creds)

    start_time, end_time = _maps_ingest_window(years_back=years_back, days_back=days_back)
    context.log.info("Maps DP window: %s → %s", start_time.isoformat(), end_time.isoformat())

    job_id = client.initiate_archive(MAPS_RESOURCES, start_time=start_time, end_time=end_time)
    job = client.wait_for_archive(job_id)

    with tempfile.TemporaryDirectory(prefix="maps-dp-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        visits, paths = parse_archive(root)

    n_visits = insert_visits(visits)
    n_paths = insert_paths(paths)
    context.log.info("Inserted %d visits, %d paths", n_visits, n_paths)
    return {"visits": n_visits, "paths": n_paths}


@asset(
    group_name="google",
    description="One-shot 1y backfill of Maps Timeline.",
    deps=[maps_schema],
    required_resource_keys={"google_auth"},
)
def maps_initial_backfill(context) -> dict:
    return _run_maps_archive(context, years_back=1.0, days_back=0)


@asset(
    group_name="google",
    description="Daily incremental Maps DP archive for the last 24h.",
    deps=[maps_schema],
    required_resource_keys={"google_auth"},
)
def maps_daily_incremental(context) -> dict:
    return _run_maps_archive(context, years_back=0, days_back=1)


@asset(
    group_name="google",
    description="Rebuild silver.maps_trips after each maps ingest.",
    deps=[maps_daily_incremental],
)
def maps_trip_segmentation(context) -> int:
    from ingestion.google.maps.trip_segmentation import segment_trips

    n = segment_trips()
    context.log.info("Wrote %d trips to silver.maps_trips", n)
    return n


# ── Jobs + schedules ───────────────────────────────────────────────────────
maps_daily_job = define_asset_job(
    "maps_daily_job",
    selection=AssetSelection.assets(maps_daily_incremental, maps_trip_segmentation),
)


maps_daily_schedule = ScheduleDefinition(
    job=maps_daily_job,
    cron_schedule="0 4 * * *",
    name="maps_daily_schedule",
    description="Daily 04:00 Maps DP incremental + trip re-segmentation.",
)


# ── YouTube ────────────────────────────────────────────────────────────────
YOUTUBE_RESOURCES = [
    "https://www.googleapis.com/auth/dataportability.youtube.watch_history",
    "https://www.googleapis.com/auth/dataportability.youtube.search_history",
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

    creds = context.resources.google_auth.get_credentials()
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
    required_resource_keys={"google_auth"},
)
def youtube_history_initial_backfill(context) -> dict:
    return _youtube_ingest(context, years_back=1.0, days_back=0)


@asset(
    group_name="google",
    description="Daily incremental YouTube history (last 24h).",
    deps=[youtube_schema],
    required_resource_keys={"google_auth"},
)
def youtube_history_daily(context) -> dict:
    return _youtube_ingest(context, years_back=0, days_back=1)


@asset(
    group_name="google",
    description="Enrich unknown YouTube videos + channels via Data API v3.",
    deps=[youtube_history_daily],
    required_resource_keys={"google_auth"},
)
def youtube_metadata_enricher(context) -> dict:
    from ingestion.google.youtube.enricher import enrich

    creds = context.resources.google_auth.get_credentials()
    counts = enrich(creds)
    context.log.info("Enricher: %s", counts)
    return counts


youtube_daily_job = define_asset_job(
    "youtube_daily_job",
    selection=AssetSelection.assets(youtube_history_daily, youtube_metadata_enricher),
)


youtube_daily_schedule = ScheduleDefinition(
    job=youtube_daily_job,
    cron_schedule="30 4 * * *",
    name="youtube_daily_schedule",
    description="Daily 04:30 YouTube DP incremental + enrichment.",
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
