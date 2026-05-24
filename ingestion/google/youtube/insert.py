"""Bulk INSERT helpers for YouTube bronze tables."""

from __future__ import annotations

from typing import Iterable

from ..._shared.clickhouse import insert_rows


def insert_watch_history(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "youtube_watch_history",
        rows,
        database="bronze",
        column_names=[
            "watched_at", "video_id", "video_title", "video_url",
            "channel_id", "channel_title", "activity_type", "is_from_ads",
        ],
    )
    return len(rows)


def insert_search_history(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "youtube_search_history",
        rows,
        database="bronze",
        column_names=["searched_at", "query"],
    )
    return len(rows)
