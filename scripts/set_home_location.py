"""Set the home anchor used for trip segmentation.

Interactive CLI: prompts for lat/lng + radius_km + label, INSERTs a row
into silver.maps_home_locations. Run once after Phase 5 lands. Re-run if you
move (a new valid_from gives a piecewise lookup).

Usage:
    .venv/bin/python scripts/set_home_location.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("set-home-location")


def _prompt(prompt: str, *, cast=str, default=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return cast(raw)
        except ValueError as e:
            print(f"  invalid: {e}")


def main() -> int:
    from ingestion._shared.clickhouse import insert_rows

    print("Configure a home anchor for trip segmentation.")
    print("Look up your home coordinates on Google Maps (right-click → copy lat/lng).\n")

    label = _prompt("Label", default="Home")
    lat = _prompt("Latitude", cast=float)
    lng = _prompt("Longitude", cast=float)
    radius_km = _prompt("Radius (km) — visits within this distance count as 'at home'", cast=float, default=5.0)
    valid_from = _prompt("Valid from (YYYY-MM-DD)", cast=date.fromisoformat, default=date.today())

    insert_rows(
        "maps_home_locations",
        [
            {
                "valid_from": valid_from,
                "lat": lat,
                "lng": lng,
                "radius_km": float(radius_km),
                "label": label,
            }
        ],
        database="silver",
        column_names=["valid_from", "lat", "lng", "radius_km", "label"],
    )
    log.info(
        "Inserted home anchor '%s' at (%.4f, %.4f) radius=%.1fkm valid_from=%s",
        label, lat, lng, radius_km, valid_from,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
