"""YouTube Data API v3 enricher.

Watches bronze.youtube_watch_history for unknown video_ids and batches them
50/call against videos.list?part=snippet,contentDetails. Similarly for
channels.list. Quota cost is 1 unit per batch — at personal scale, well
inside the 10k/day default.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterable

from googleapiclient.discovery import build

from ..._shared.clickhouse import get_client, insert_rows


log = logging.getLogger(__name__)

BATCH_SIZE = 50

# Subset of YouTube categories — names lifted from the v3 videoCategories list
# (US region). Anything missing falls back to category_id "0" → "Uncategorized".
YOUTUBE_CATEGORY_NAMES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "18": "Short Movies",
    "19": "Travel & Events",
    "20": "Gaming",
    "21": "Videoblogging",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
    "30": "Movies",
    "31": "Anime/Animation",
    "32": "Action/Adventure",
    "33": "Classics",
    "34": "Comedy",
    "35": "Documentary",
    "36": "Drama",
    "37": "Family",
    "38": "Foreign",
    "39": "Horror",
    "40": "Sci-Fi/Fantasy",
    "41": "Thriller",
    "42": "Shorts",
    "43": "Shows",
    "44": "Trailers",
}


_ISO8601_DURATION = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?"
)


def _parse_iso_duration(raw: str | None) -> int:
    if not raw:
        return 0
    m = _ISO8601_DURATION.match(raw)
    if not m:
        return 0
    h, mn, s = m.groups()
    return int(h or 0) * 3600 + int(mn or 0) * 60 + int(float(s or 0))


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


def _missing_video_ids(client) -> list[str]:
    sql = (
        "SELECT DISTINCT video_id FROM bronze.youtube_watch_history "
        "WHERE video_id != '' AND video_id NOT IN ("
        "  SELECT video_id FROM bronze.youtube_videos"
        ") LIMIT 1000"
    )
    return [row[0] for row in client.query(sql).result_rows]


def _missing_channel_ids(client) -> list[str]:
    sql = (
        "SELECT DISTINCT channel_id FROM bronze.youtube_videos "
        "WHERE channel_id != '' AND channel_id NOT IN ("
        "  SELECT channel_id FROM bronze.youtube_channels"
        ") LIMIT 1000"
    )
    return [row[0] for row in client.query(sql).result_rows]


def _video_row(v: dict) -> dict:
    snippet = v.get("snippet") or {}
    content = v.get("contentDetails") or {}
    return {
        "video_id": v.get("id") or "",
        "video_title": snippet.get("title") or "",
        "channel_id": snippet.get("channelId") or "",
        "category_id": snippet.get("categoryId") or "",
        "duration_seconds": _parse_iso_duration(content.get("duration")),
        "published_at": datetime.fromisoformat(
            (snippet.get("publishedAt") or "1970-01-01T00:00:00Z").replace("Z", "+00:00")
        ).replace(tzinfo=None),
        "default_language": snippet.get("defaultLanguage") or "",
    }


def _channel_row(ch: dict) -> dict:
    snippet = ch.get("snippet") or {}
    statistics = ch.get("statistics") or {}
    thumbnails = (snippet.get("thumbnails") or {}).get("default") or {}
    # primary_category_name: YouTube doesn't return a category on channels.list,
    # so we leave it empty here — gold tables derive it from the videos table.
    return {
        "channel_id": ch.get("id") or "",
        "channel_title": snippet.get("title") or "",
        "primary_category_name": "",
        "subscriber_count": int(statistics.get("subscriberCount") or 0),
        "thumbnail_url": thumbnails.get("url") or "",
    }


def _video_tombstone(video_id: str) -> dict:
    """Placeholder row for a video the Data API can't return (deleted, private,
    or region-locked). Recording the attempt is what makes enrichment converge:
    without it the id stays in the "missing" set forever and the sensor re-fires
    every interval. silver_youtube_watches falls back to the watch-history
    title/channel for tombstoned ids, so nothing is lost on screen."""
    return {
        "video_id": video_id,
        "video_title": "",
        "channel_id": "",
        "category_id": "",
        "duration_seconds": 0,
        "published_at": datetime(1970, 1, 1),
        "default_language": "",
    }


def _channel_tombstone(channel_id: str) -> dict:
    """Placeholder for a channel the Data API can't return — same convergence
    rationale as _video_tombstone."""
    return {
        "channel_id": channel_id,
        "channel_title": "",
        "primary_category_name": "",
        "subscriber_count": 0,
        "thumbnail_url": "",
    }


def enrich(creds) -> dict[str, int]:
    """Run one enrichment pass. Returns inserted counts.

    Every requested id is written back — real metadata when the API returns it,
    a tombstone when it doesn't — so the worklist drains and the enricher sensor
    stops firing once all known ids have been attempted."""

    svc = build("youtube", "v3", credentials=creds, cache_discovery=False)
    client = get_client()

    counts = {"videos": 0, "channels": 0, "video_tombstones": 0, "channel_tombstones": 0}

    for batch in _chunked(_missing_video_ids(client), BATCH_SIZE):
        try:
            resp = svc.videos().list(id=",".join(batch), part="snippet,contentDetails").execute()
        except Exception as exc:
            # Transient (quota/network/auth) — skip without tombstoning so the
            # ids are retried next run rather than permanently marked missing.
            log.warning("videos.list batch of %d failed, retrying next run: %s", len(batch), exc)
            continue
        rows = [_video_row(v) for v in (resp.get("items") or [])]
        returned = {r["video_id"] for r in rows}
        tombstones = [_video_tombstone(vid) for vid in batch if vid not in returned]
        all_rows = rows + tombstones
        if all_rows:
            insert_rows(
                "youtube_videos",
                all_rows,
                database="bronze",
                column_names=[
                    "video_id", "video_title", "channel_id", "category_id",
                    "duration_seconds", "published_at", "default_language",
                ],
            )
            counts["videos"] += len(rows)
            counts["video_tombstones"] += len(tombstones)

    for batch in _chunked(_missing_channel_ids(client), BATCH_SIZE):
        try:
            resp = svc.channels().list(id=",".join(batch), part="snippet,statistics").execute()
        except Exception as exc:
            log.warning("channels.list batch of %d failed, retrying next run: %s", len(batch), exc)
            continue
        rows = [_channel_row(ch) for ch in (resp.get("items") or [])]
        returned = {r["channel_id"] for r in rows}
        tombstones = [_channel_tombstone(cid) for cid in batch if cid not in returned]
        all_rows = rows + tombstones
        if all_rows:
            insert_rows(
                "youtube_channels",
                all_rows,
                database="bronze",
                column_names=[
                    "channel_id", "channel_title", "primary_category_name",
                    "subscriber_count", "thumbnail_url",
                ],
            )
            counts["channels"] += len(rows)
            counts["channel_tombstones"] += len(tombstones)

    log.info(
        "Enrichment: +%d videos (+%d tombstones), +%d channels (+%d tombstones)",
        counts["videos"], counts["video_tombstones"],
        counts["channels"], counts["channel_tombstones"],
    )
    return counts
