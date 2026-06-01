"""Lazy enrichment for unknown track_ids and artist_ids in bronze.

Run as a Dagster sensor every ~10 min — picks up new IDs as they land in
bronze.spotify_plays_raw / bronze.spotify_saved_tracks, fetches metadata in
batches of 50 against /tracks?ids and /artists?ids, and INSERTs into
bronze.spotify_tracks / bronze.spotify_artists.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

from .._shared.clickhouse import get_client, insert_rows


log = logging.getLogger(__name__)

BATCH_SIZE = 50


def _chunked(items: Iterable[str], n: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for x in items:
        if not x:
            continue
        batch.append(x)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def _parse_release_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        # bronze.spotify_tracks.album_release_date is Date32 (1900-2299); clamp
        # out-of-range values to NULL so a stray date can't break the insert.
        return parsed if 1900 <= parsed.year <= 2299 else None
    return None


def _missing_track_ids(client) -> list[str]:
    sql = (
        "SELECT DISTINCT track_id FROM bronze.spotify_plays_raw "
        "WHERE track_id != '' AND track_id NOT IN ("
        "  SELECT track_id FROM bronze.spotify_tracks"
        ") LIMIT 500"
    )
    return [row[0] for row in client.query(sql).result_rows]


def _missing_artist_ids(client) -> list[str]:
    sql = (
        "SELECT DISTINCT arrayJoin(artists_ids) AS artist_id "
        "FROM bronze.spotify_plays_raw "
        "WHERE artist_id != '' AND artist_id NOT IN ("
        "  SELECT artist_id FROM bronze.spotify_artists"
        ") LIMIT 500"
    )
    return [row[0] for row in client.query(sql).result_rows]


def _track_row(t: dict[str, Any]) -> dict[str, Any]:
    album = t.get("album") or {}
    return {
        "track_id": t.get("id") or "",
        "track_name": t.get("name") or "",
        "track_uri": t.get("uri") or "",
        "duration_ms": int(t.get("duration_ms") or 0),
        "explicit": bool(t.get("explicit")),
        "popularity": int(t.get("popularity") or 0),
        "isrc": (t.get("external_ids") or {}).get("isrc") or "",
        "album_id": album.get("id") or "",
        "album_name": album.get("name") or "",
        "album_uri": album.get("uri") or "",
        "album_images": [img.get("url", "") for img in (album.get("images") or [])],
        "album_release_date": _parse_release_date(album.get("release_date")),
        "artists_ids": [a.get("id", "") for a in (t.get("artists") or [])],
    }


def _artist_row(a: dict[str, Any]) -> dict[str, Any]:
    images = a.get("images") or []
    followers = (a.get("followers") or {}).get("total") or 0
    return {
        "artist_id": a.get("id") or "",
        "artist_name": a.get("name") or "",
        "artist_uri": a.get("uri") or "",
        "genres": list(a.get("genres") or []),
        "popularity": int(a.get("popularity") or 0),
        "followers": int(followers),
        "image_url": images[0]["url"] if images and images[0].get("url") else "",
    }


def enrich(sp) -> dict[str, int]:
    """Run one enrichment pass; returns counts for logging."""

    client = get_client()
    counts = {"tracks": 0, "artists": 0}

    track_ids = _missing_track_ids(client)
    for batch in _chunked(track_ids, BATCH_SIZE):
        resp = sp.tracks(batch)
        rows = [_track_row(t) for t in (resp.get("tracks") or []) if t]
        if rows:
            insert_rows("spotify_tracks", rows, database="bronze")
            counts["tracks"] += len(rows)

    artist_ids = _missing_artist_ids(client)
    for batch in _chunked(artist_ids, BATCH_SIZE):
        resp = sp.artists(batch)
        rows = [_artist_row(a) for a in (resp.get("artists") or []) if a]
        if rows:
            insert_rows("spotify_artists", rows, database="bronze")
            counts["artists"] += len(rows)

    log.info("Enrichment: +%d tracks, +%d artists", counts["tracks"], counts["artists"])
    return counts
