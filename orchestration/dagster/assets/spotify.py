"""Spotify Dagster assets.

Phase 1: schema bootstrap. The long-running currently-playing producer is a
separate compose service (spotify-current-producer), not a Dagster asset.
Phase 2: scheduled pulls (recently-played, saved tracks) + lazy enricher.
"""

from __future__ import annotations

from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    ScheduleDefinition,
    SensorEvaluationContext,
    RunRequest,
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


@asset(group_name="spotify", description="DDL bootstrap for Spotify currently-playing.")
def spotify_current_track_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    execute_file(str(_ddl_path("10_spotify_current_track.sql")))
    return "ok"


@asset(group_name="spotify", description="DDL bootstrap for Spotify history + catalogs.")
def spotify_history_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    execute_file(str(_ddl_path("20_spotify_history.sql")))
    return "ok"


@asset(
    group_name="spotify",
    description="Pull /me/player/recently-played and INSERT into bronze.spotify_plays_raw.",
    deps=[spotify_history_schema],
    required_resource_keys={"spotify"},
)
def spotify_recently_played(context) -> int:
    from ingestion.spotify.recently_played import fetch_and_store

    sp = context.resources.spotify.get_client()
    n = fetch_and_store(sp, stage_to_r2=False)
    context.log.info("Inserted %d plays", n)
    return n


@asset(
    group_name="spotify",
    description="Pull /me/tracks and INSERT into bronze.spotify_saved_tracks.",
    deps=[spotify_history_schema],
    required_resource_keys={"spotify"},
)
def spotify_saved_tracks(context) -> int:
    from ingestion.spotify.saved_tracks import fetch_and_store

    sp = context.resources.spotify.get_client()
    n = fetch_and_store(sp)
    context.log.info("Inserted %d saved tracks", n)
    return n


@asset(
    group_name="spotify",
    description="Enrich missing track/artist IDs via /tracks?ids + /artists?ids.",
    deps=[spotify_recently_played],
    required_resource_keys={"spotify"},
)
def spotify_metadata_enricher(context) -> dict:
    from ingestion.spotify.enrichment import enrich

    sp = context.resources.spotify.get_client()
    counts = enrich(sp)
    context.log.info("Enriched: %s", counts)
    return counts


# ── Jobs + schedules + sensor ──────────────────────────────────────────────
spotify_recently_played_job = define_asset_job(
    "spotify_recently_played_job",
    selection=AssetSelection.assets(spotify_recently_played),
)

spotify_saved_tracks_job = define_asset_job(
    "spotify_saved_tracks_job",
    selection=AssetSelection.assets(spotify_saved_tracks),
)

spotify_enricher_job = define_asset_job(
    "spotify_enricher_job",
    selection=AssetSelection.assets(spotify_metadata_enricher),
)


spotify_recently_played_schedule = ScheduleDefinition(
    job=spotify_recently_played_job,
    cron_schedule="*/1 * * * *",
    name="spotify_recently_played_schedule",
    description="Pull recently-played every minute.",
)


spotify_saved_tracks_schedule = ScheduleDefinition(
    job=spotify_saved_tracks_job,
    cron_schedule="*/5 * * * *",
    name="spotify_saved_tracks_schedule",
    description="Pull saved tracks every 5 minutes.",
)


@sensor(
    job=spotify_enricher_job,
    minimum_interval_seconds=600,
    name="spotify_metadata_enricher_sensor",
    description="Trigger an enrichment run when bronze has unknown track/artist IDs.",
)
def spotify_metadata_enricher_sensor(context: SensorEvaluationContext):
    """Fire when bronze.spotify_plays_raw has track_ids missing from bronze.spotify_tracks.

    We don't pull from Spotify here — that happens in the asset run. This sensor
    just decides whether to trigger one.
    """
    from ingestion._shared.clickhouse import get_client

    try:
        client = get_client()
        n_missing_tracks = client.query(
            "SELECT count(DISTINCT track_id) FROM bronze.spotify_plays_raw "
            "WHERE track_id != '' AND track_id NOT IN (SELECT track_id FROM bronze.spotify_tracks)"
        ).result_rows[0][0]
        n_missing_artists = client.query(
            "SELECT count(DISTINCT arrayJoin(artists_ids)) FROM bronze.spotify_plays_raw "
            "WHERE notEmpty(artists_ids) AND arrayJoin(artists_ids) NOT IN ("
            "  SELECT artist_id FROM bronze.spotify_artists"
            ")"
        ).result_rows[0][0]
    except Exception as exc:
        return SkipReason(f"sensor check failed (likely tables missing yet): {exc}")

    if (n_missing_tracks or 0) + (n_missing_artists or 0) == 0:
        return SkipReason("no unknown IDs in bronze")

    return RunRequest(
        run_key=f"enrich-tracks{n_missing_tracks}-artists{n_missing_artists}",
        tags={"missing_tracks": str(n_missing_tracks), "missing_artists": str(n_missing_artists)},
    )
