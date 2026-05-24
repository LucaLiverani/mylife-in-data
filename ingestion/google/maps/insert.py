"""Bulk INSERT helpers for Maps bronze tables."""

from __future__ import annotations

from typing import Iterable

from ..._shared.clickhouse import insert_rows


def insert_visits(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "maps_visits",
        rows,
        database="bronze",
        column_names=[
            "started_at",
            "ended_at",
            "place_name",
            "place_id",
            "place_address",
            "lat",
            "lng",
            "confidence",
        ],
    )
    return len(rows)


def insert_paths(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "maps_path",
        rows,
        database="bronze",
        column_names=[
            "started_at",
            "ended_at",
            "start_lat",
            "start_lng",
            "end_lat",
            "end_lng",
            "distance_m",
            "activity_type",
        ],
    )
    return len(rows)
