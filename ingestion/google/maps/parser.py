"""Parse the Maps Timeline JSON inside a Data Portability archive.

The DP archive mirrors Google Takeout's layout. Timeline files live at
"Takeout/Location History (Timeline)/Records.json" (older exports use
per-month files). Each entry is either a `placeVisit` or an `activitySegment`.

This parser is tolerant: missing/null fields collapse to sensible defaults.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..portability import walk_files


log = logging.getLogger(__name__)


def _e7_to_deg(value: int | float | None) -> float:
    """Many Timeline fields store coordinates as integer * 1e7."""
    if value is None:
        return 0.0
    if abs(value) > 360:
        return float(value) / 1e7
    return float(value)


def _parse_ts(value: str | int | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / (1000 if value > 1e12 else 1), tz=None)
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # Some Takeout dumps use "2022-01-30T14:23:00.000+00:00" — handled above.
        # Older dumps used "2022-01-30T14:23:00Z" (also handled).
        return None


def _row_from_place_visit(pv: dict[str, Any]) -> dict[str, Any] | None:
    duration = pv.get("duration") or {}
    started = _parse_ts(duration.get("startTimestamp"))
    ended = _parse_ts(duration.get("endTimestamp"))
    if not started or not ended:
        return None
    location = pv.get("location") or {}
    return {
        "started_at": started,
        "ended_at": ended,
        "place_name": location.get("name") or "",
        "place_id": location.get("placeId") or "",
        "place_address": location.get("address") or "",
        "lat": _e7_to_deg(location.get("latitudeE7") or location.get("latitude")),
        "lng": _e7_to_deg(location.get("longitudeE7") or location.get("longitude")),
        "confidence": float(pv.get("locationConfidence") or 0.0) / 100.0 if pv.get("locationConfidence") else 0.0,
    }


def _row_from_activity_segment(seg: dict[str, Any]) -> dict[str, Any] | None:
    duration = seg.get("duration") or {}
    started = _parse_ts(duration.get("startTimestamp"))
    ended = _parse_ts(duration.get("endTimestamp"))
    if not started or not ended:
        return None
    start_loc = seg.get("startLocation") or {}
    end_loc = seg.get("endLocation") or {}
    return {
        "started_at": started,
        "ended_at": ended,
        "start_lat": _e7_to_deg(start_loc.get("latitudeE7") or start_loc.get("latitude")),
        "start_lng": _e7_to_deg(start_loc.get("longitudeE7") or start_loc.get("longitude")),
        "end_lat": _e7_to_deg(end_loc.get("latitudeE7") or end_loc.get("latitude")),
        "end_lng": _e7_to_deg(end_loc.get("longitudeE7") or end_loc.get("longitude")),
        "distance_m": int(seg.get("distance") or 0),
        "activity_type": (seg.get("activityType") or "").lower(),
    }


def _records_in_file(path: Path) -> Iterator[dict[str, Any]]:
    """Yield records from a Timeline JSON file.

    Handles three known shapes:
      - Old Takeout: `{"timelineObjects": [...]}`
      - DP archive:  `[{...}, {...}]` (top-level list)
      - MyActivity:  `[{"header": "Maps", "title": "...", ...}]`

    Returns whatever it can find; downstream code filters by content shape
    (placeVisit / activitySegment / activity entries)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.warning("skipping unreadable file: %s", path)
        return

    if isinstance(data, list):
        for obj in data:
            if isinstance(obj, dict):
                yield obj
        return

    if isinstance(data, dict):
        objects = data.get("timelineObjects") or data.get("locations") or []
        for obj in objects:
            if isinstance(obj, dict):
                yield obj


def parse_archive(root: Path) -> tuple[list[dict], list[dict]]:
    """Walk the unpacked DP archive, return (visits, paths) bronze-row lists."""

    visits: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []

    # Try the modern path first; fall back to walking for any Records.json /
    # 2024_JANUARY.json-style file we find.
    candidates: Iterable[Path]
    timeline_root = root / "Takeout" / "Location History (Timeline)"
    if timeline_root.exists():
        candidates = list(timeline_root.rglob("*.json"))
    else:
        candidates = list(walk_files(root, ".json"))

    for path in candidates:
        for obj in _records_in_file(path):
            if "placeVisit" in obj:
                row = _row_from_place_visit(obj["placeVisit"])
                if row:
                    visits.append(row)
            if "activitySegment" in obj:
                row = _row_from_activity_segment(obj["activitySegment"])
                if row:
                    paths.append(row)

    log.info("Parsed %d visits, %d activity segments from %s", len(visits), len(paths), root)
    return visits, paths
