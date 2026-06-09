"""Spotify recently-played: pull /me/player/recently-played and INSERT into bronze.

Idempotent: dedup happens at the ReplacingMergeTree layer on (track_id, played_at).
The R2 cold copy happens downstream: the nightly warehouse_r2_archive job
snapshots bronze.spotify_plays_raw (and every other bronze table) to Parquet.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .._shared.clickhouse import insert_rows


log = logging.getLogger(__name__)


def _parse_played_at(value: str) -> datetime:
    # Spotify returns ISO-8601 with 'Z'. fromisoformat handles +HH:MM but not 'Z'.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_from_play(play: dict[str, Any]) -> dict[str, Any]:
    track = play.get("track") or {}
    artists = track.get("artists") or []
    album = track.get("album") or {}
    context = play.get("context") or {}
    # The recently-played payload embeds the full track object, so we capture
    # name/album/art/artist-names here rather than waiting for the enricher's
    # second round-trip to /tracks?ids. The enricher still backfills the catalog
    # tables (genres, popularity, saved tracks); silver prefers those when present.
    return {
        "played_at": _parse_played_at(play["played_at"]),
        "track_id": track.get("id") or "",
        "track_uri": track.get("uri") or "",
        "track_name": track.get("name") or "",
        "artists_ids": [a.get("id", "") for a in artists],
        "artists_names": [a.get("name", "") for a in artists],
        "album_name": album.get("name") or "",
        "album_images": [img.get("url", "") for img in (album.get("images") or [])],
        "duration_ms": int(track.get("duration_ms") or 0),
        "context_type": (context.get("type") or "") or "",
        "context_uri": (context.get("uri") or "") or "",
    }


def fetch_and_store(sp) -> int:
    """Fetch the last 50 plays, INSERT bronze, return row count."""

    response = sp.current_user_recently_played(limit=50)
    items = response.get("items") or []
    if not items:
        log.info("Spotify recently-played: empty response")
        return 0

    rows = [_row_from_play(p) for p in items]
    insert_rows("spotify_plays_raw", rows, database="bronze")
    log.info("Inserted %d plays into bronze.spotify_plays_raw", len(rows))
    return len(rows)
