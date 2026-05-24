"""Parse Google's MyActivity.json for Maps into bronze.maps_activity rows.

Each entry in MyActivity.json looks like:
  {
    "header": "Maps",
    "title": "African Queen" | "Searched for X" | "Directions to Y" | "Used Maps",
    "titleUrl": "http://maps.google.com/maps?q=…&ftid=…",
    "time": "2026-05-24T18:10:44.123Z",
    "products": ["Maps"]
  }

We classify activity_type from the title prefix and extract structured fields
where present. Coordinates aren't usually in the URL directly (Google encodes
them as an ftid hash), so most rows leave lat/lng=0; the Places API enricher
fills them in via place_id lookup later.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)


# Matches `?q=...` and `&q=...` parameters in a Google Maps URL.
_RE_QUERY = re.compile(r"[?&]q=([^&]+)")
# Matches `&ftid=0xHEX:0xHEX` — Google's internal place hash.
_RE_FTID = re.compile(r"[?&]ftid=([0-9a-fA-Fx:]+)")
# Matches `&daddr=…` (destination) and `&saddr=…` (source) on directions URLs.
_RE_DADDR = re.compile(r"[?&]daddr=([^&]+)")
_RE_SADDR = re.compile(r"[?&]saddr=([^&]+)")
# Some Maps URLs embed lat/lng as `!3dLAT!4dLNG` in the path.
_RE_LATLNG_BANG = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _url_decode(value: str) -> str:
    try:
        return urllib.parse.unquote_plus(value)
    except Exception:
        return value


def _extract_query(url: str) -> str:
    m = _RE_QUERY.search(url)
    return _url_decode(m.group(1)) if m else ""


def _extract_ftid(url: str) -> str:
    m = _RE_FTID.search(url)
    return m.group(1) if m else ""


def _extract_latlng(url: str) -> tuple[float, float]:
    m = _RE_LATLNG_BANG.search(url)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass
    return 0.0, 0.0


def _classify(title: str) -> tuple[str, str, str, str, str]:
    """Returns (activity_type, query, place_name, origin, destination).

    Title prefixes seen in real exports:
      "Searched for X"            → search
      "Directions to Y"           → directions (destination=Y)
      "Directions from X to Y"    → directions (origin=X, destination=Y)
      "Viewed area around X"      → view_place (place_name=X)
      "Used Maps"                 → other
      "<Place Name>"              → view_place (place_name=title)
    """
    title = (title or "").strip()
    if not title:
        return ("other", "", "", "", "")

    if title.startswith("Searched for "):
        return ("search", title[len("Searched for "):].strip(), "", "", "")

    if title.startswith("Directions from "):
        rest = title[len("Directions from "):]
        if " to " in rest:
            origin, destination = rest.split(" to ", 1)
            return ("directions", "", "", origin.strip(), destination.strip())
        return ("directions", "", "", rest.strip(), "")

    if title.startswith("Directions to "):
        return ("directions", "", "", "", title[len("Directions to "):].strip())

    if title.startswith("Viewed area around "):
        return ("view_place", "", title[len("Viewed area around "):].strip(), "", "")

    if title.startswith("Used Maps") or title.startswith("Used the "):
        return ("other", "", "", "", "")

    # Default: a place name → place was viewed/opened.
    return ("view_place", "", title, "", "")


def _row(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry.get("header") != "Maps":
        return None
    ts = _parse_ts(entry.get("time"))
    if not ts:
        return None
    title = entry.get("title", "") or ""
    url = entry.get("titleUrl", "") or ""

    activity_type, query, place_name, origin, destination = _classify(title)

    # If we couldn't pull a query from the title, try the URL ?q= param.
    if activity_type == "search" and not query:
        query = _extract_query(url)
    # If a place URL has a q= parameter but no name in title, use the q.
    if activity_type == "view_place" and not place_name:
        place_name = _extract_query(url)

    lat, lng = _extract_latlng(url)
    ftid = _extract_ftid(url)

    return {
        "event_ts": ts,
        "activity_type": activity_type,
        "query": query,
        "place_name": place_name,
        "place_id": ftid,
        "lat": lat,
        "lng": lng,
        "origin": origin,
        "destination": destination,
        "raw_url": url,
    }


def parse_my_activity(path: Path) -> list[dict[str, Any]]:
    """Parse a MyActivity.json file. Tolerant: returns rows it can classify,
    skips entries that aren't Maps-related or lack a timestamp."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("skipping unreadable file %s: %s", path, exc)
        return []

    if not isinstance(data, list):
        log.warning("expected top-level list in %s, got %s", path, type(data).__name__)
        return []

    rows: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        row = _row(entry)
        if row:
            rows.append(row)
    log.info("Parsed %d Maps activity rows from %s", len(rows), path.name)
    return rows


def parse_archive_for_activity(root: Path) -> list[dict[str, Any]]:
    """Walk a DP archive root for MyActivity/Maps/MyActivity.json (and any
    similarly-named per-month files in older exports)."""
    paths: list[Path] = []
    target_dir = root / "Portability" / "My Activity" / "Maps"
    if target_dir.exists():
        paths.extend(target_dir.rglob("*.json"))
    else:
        # Fallback for unexpected layouts: scan for any file under My Activity/Maps.
        for path in root.rglob("MyActivity.json"):
            if "Maps" in path.parts:
                paths.append(path)

    rows: list[dict[str, Any]] = []
    for p in paths:
        rows.extend(parse_my_activity(p))
    return rows


# ── Saved Places (coords-only, for the private filter) ────────────────────
def parse_starred_places_coords(root: Path) -> list[dict[str, float]]:
    """Extract ONLY lat/lng from the starred-places GeoJSON.

    We deliberately do not return names, addresses, or comments — the
    starred-places file contains friends' home addresses and those values
    must not enter the warehouse beyond the spatial filter.
    """
    candidates = [
        root / "Portability" / "Maps (your places)" / "Saved Places.json",
        root / "Portability" / "Maps" / "Saved Places.json",
    ]
    rows: list[dict[str, float]] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("skipping unreadable %s", path)
            continue
        for feature in data.get("features", []) or []:
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or [0, 0]
            try:
                # GeoJSON is [lng, lat] not [lat, lng].
                lng = float(coords[0])
                lat = float(coords[1])
            except (ValueError, IndexError, TypeError):
                continue
            if lat == 0 and lng == 0:
                continue
            rows.append({"lat": lat, "lng": lng, "radius_m": 100})
    log.info("Extracted %d private-place coordinates from starred places", len(rows))
    return rows
