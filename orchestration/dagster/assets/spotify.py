"""Spotify Dagster assets.

Phase 1: schema bootstrap asset only. The long-running currently-playing
producer is a separate compose service (spotify-current-producer), not a
Dagster asset — the schedule cadence (5s) is too tight for Dagster's run
machinery, and we'd be paying scheduler overhead for nothing.
"""

from __future__ import annotations

from pathlib import Path

from dagster import AssetExecutionContext, asset


REPO_ROOT_IN_CONTAINER = Path("/opt/dagster/repo")


@asset(group_name="spotify", description="Idempotent DDL bootstrap for Spotify bronze tables + MV.")
def spotify_current_track_schema(context: AssetExecutionContext) -> str:
    """Apply warehouse/ddl/10_spotify_current_track.sql against ClickHouse."""

    from ingestion._shared.clickhouse import execute_file

    ddl_path = REPO_ROOT_IN_CONTAINER / "warehouse" / "ddl" / "10_spotify_current_track.sql"
    if not ddl_path.exists():
        # Outside container (e.g. local dev), resolve from this file.
        ddl_path = Path(__file__).resolve().parents[3] / "warehouse" / "ddl" / "10_spotify_current_track.sql"

    execute_file(str(ddl_path))
    context.log.info("Applied %s", ddl_path)
    return "ok"
