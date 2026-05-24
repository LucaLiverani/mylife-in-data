"""Spotify recently-played: pull /me/player/recently-played and INSERT into bronze.

Idempotent: dedup happens at the ReplacingMergeTree layer on (track_id, played_at).
Optionally stages the raw API response to R2 for replay.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from .._shared.clickhouse import insert_rows
from .._shared.json_utils import dumps
from .._shared.r2 import upload_bytes


log = logging.getLogger(__name__)


def _parse_played_at(value: str) -> datetime:
    # Spotify returns ISO-8601 with 'Z'. fromisoformat handles +HH:MM but not 'Z'.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_from_play(play: dict[str, Any]) -> dict[str, Any]:
    track = play.get("track") or {}
    artists = track.get("artists") or []
    context = play.get("context") or {}
    return {
        "played_at": _parse_played_at(play["played_at"]),
        "track_id": track.get("id") or "",
        "track_uri": track.get("uri") or "",
        "artists_ids": [a.get("id", "") for a in artists],
        "duration_ms": int(track.get("duration_ms") or 0),
        "context_type": (context.get("type") or "") or "",
        "context_uri": (context.get("uri") or "") or "",
    }


def fetch_and_store(sp, *, stage_to_r2: bool = False) -> int:
    """Fetch the last 50 plays, INSERT bronze, return row count."""

    response = sp.current_user_recently_played(limit=50)
    items = response.get("items") or []
    if not items:
        log.info("Spotify recently-played: empty response")
        return 0

    rows = [_row_from_play(p) for p in items]
    insert_rows("spotify_plays_raw", rows, database="bronze")
    log.info("Inserted %d plays into bronze.spotify_plays_raw", len(rows))

    if stage_to_r2 and os.environ.get("R2_BUCKET"):
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        run_id = datetime.now(tz=timezone.utc).strftime("%H%M%S%f")
        key = f"spotify/plays/{today}/{run_id}.json"
        try:
            upload_bytes(key, dumps(response).encode("utf-8"), content_type="application/json")
            log.info("Staged response to r2://%s/%s", os.environ.get("R2_BUCKET"), key)
        except Exception:
            log.exception("R2 upload failed (continuing)")

    return len(rows)
