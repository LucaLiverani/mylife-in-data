"""Bulk INSERT helpers for Maps bronze + silver tables."""

from __future__ import annotations

from typing import Iterable

from ..._shared.clickhouse import insert_rows


def insert_activity(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "maps_activity",
        rows,
        database="bronze",
        column_names=[
            "event_ts", "activity_type", "query", "place_name", "place_id",
            "lat", "lng", "origin", "destination", "raw_url",
        ],
    )
    return len(rows)


def insert_private_places(rows: Iterable[dict]) -> int:
    """Populate silver.maps_private_places. Input is coords-only —
    NEVER include names; this table backs the privacy filter."""
    rows = list(rows)
    if not rows:
        return 0
    insert_rows(
        "maps_private_places",
        rows,
        database="silver",
        column_names=["lat", "lng", "radius_m"],
    )
    return len(rows)
