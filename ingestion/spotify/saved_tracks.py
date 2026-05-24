"""Spotify saved tracks ("Liked"): paginates /me/tracks and INSERTs bronze.

Polls every 5 min from Dagster; ReplacingMergeTree deduplicates by
(track_id, added_at). Used for the "Liked" rows in /api/now/timeline.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .._shared.clickhouse import insert_rows


log = logging.getLogger(__name__)


def _parse_added_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row(saved: dict[str, Any]) -> dict[str, Any]:
    track = saved.get("track") or {}
    return {
        "added_at": _parse_added_at(saved["added_at"]),
        "track_id": track.get("id") or "",
        "track_uri": track.get("uri") or "",
    }


def fetch_and_store(sp, *, max_pages: int = 4) -> int:
    """Fetch saved tracks in 50-row pages; cap at max_pages * 50 to bound runtime.

    Steady-state poll only needs the newest page or two; the cap protects the
    initial seed from being unbounded."""

    total = 0
    offset = 0
    for _ in range(max_pages):
        resp = sp.current_user_saved_tracks(limit=50, offset=offset)
        items = resp.get("items") or []
        if not items:
            break
        rows = [_row(i) for i in items]
        insert_rows("spotify_saved_tracks", rows, database="bronze")
        total += len(rows)
        offset += len(items)
        if not resp.get("next"):
            break
    log.info("Inserted %d saved tracks into bronze.spotify_saved_tracks", total)
    return total
