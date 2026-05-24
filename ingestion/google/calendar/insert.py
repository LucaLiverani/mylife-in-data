"""Bulk INSERT helpers for Calendar bronze tables."""

from __future__ import annotations

from typing import Iterable

from ..._shared.clickhouse import insert_rows


def insert_events(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "calendar_events",
        rows,
        database="bronze",
        column_names=[
            "event_id", "calendar_id", "calendar_name", "started_at", "ended_at",
            "title", "description", "location", "status", "attendee_count",
            "recurrence_id",
        ],
    )
    return len(rows)
