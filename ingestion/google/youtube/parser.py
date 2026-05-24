"""Parse YouTube watch + search history JSON inside a DP archive.

YouTube history exports live at "Takeout/YouTube and YouTube Music/history/"
with files watch-history.json and search-history.json. Each entry is a
{title, titleUrl, time, subtitles?, details?, ...} record.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..portability import walk_files


log = logging.getLogger(__name__)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


_VIDEO_ID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")


def _extract_video_id(url: str) -> str:
    if not url:
        return ""
    m = _VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)
    # Short URLs like https://youtu.be/<id>
    if "youtu.be/" in url:
        candidate = url.split("youtu.be/", 1)[1].split("?", 1)[0]
        if len(candidate) == 11:
            return candidate
    return ""


def _channel_from_subtitles(entry: dict[str, Any]) -> tuple[str, str]:
    subs = entry.get("subtitles") or []
    if not subs:
        return "", ""
    first = subs[0] or {}
    channel_url = first.get("url") or ""
    channel_id = channel_url.split("/channel/", 1)[-1] if "/channel/" in channel_url else ""
    return channel_id, first.get("name") or ""


def _watch_row(entry: dict[str, Any]) -> dict[str, Any] | None:
    title_url = entry.get("titleUrl") or ""
    video_id = _extract_video_id(title_url)
    if not video_id:
        return None
    watched_at = _parse_ts(entry.get("time"))
    if not watched_at:
        return None

    title = entry.get("title") or ""
    if title.startswith("Watched "):
        title = title[len("Watched "):]

    channel_id, channel_title = _channel_from_subtitles(entry)

    details = entry.get("details") or []
    is_ads = any("From Google Ads" in (d.get("name") or "") for d in details if isinstance(d, dict))

    return {
        "watched_at": watched_at,
        "video_id": video_id,
        "video_title": title,
        "video_url": title_url,
        "channel_id": channel_id,
        "channel_title": channel_title,
        "activity_type": "watched",
        "is_from_ads": is_ads,
    }


def _search_row(entry: dict[str, Any]) -> dict[str, Any] | None:
    title = entry.get("title") or ""
    if not title.startswith("Searched for "):
        return None
    query = title[len("Searched for "):]
    when = _parse_ts(entry.get("time"))
    if not when:
        return None
    return {"searched_at": when, "query": query}


def parse_archive(root: Path) -> tuple[list[dict], list[dict]]:
    """Walk the unpacked DP archive, return (watch_rows, search_rows)."""

    watch: list[dict[str, Any]] = []
    search: list[dict[str, Any]] = []

    yt_root = root / "Takeout" / "YouTube and YouTube Music"
    candidates = list(yt_root.rglob("*.json")) if yt_root.exists() else list(walk_files(root, ".json"))

    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, list):
            continue

        # File can be either watch-history or search-history; rows are tagged
        # via the "header" key but the safest classifier is the title prefix.
        for entry in data:
            row = _watch_row(entry)
            if row:
                watch.append(row)
                continue
            srow = _search_row(entry)
            if srow:
                search.append(srow)

    log.info("Parsed %d watch + %d search entries from %s", len(watch), len(search), root)
    return watch, search
