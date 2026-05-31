"""Import a manual on-device Maps Timeline export.

Use this when the Data Portability API returns no Maps data (post-2024
on-device migration). Export Timeline from the phone (Google Maps → Settings
→ Personal content → Export Timeline), drop the resulting ZIP or extracted
folder onto your laptop, and pass its path here.

Usage:
    .venv/bin/python scripts/import_maps_timeline_export.py /path/to/export.zip
    .venv/bin/python scripts/import_maps_timeline_export.py /path/to/Takeout/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

# Host-run tool: the .env's CLICKHOUSE_HOST targets the Docker network
# ("clickhouse"), which the VM host can't resolve. Default to localhost (the
# published port) unless CLICKHOUSE_HOST was set explicitly in the shell.
_ch_host = os.environ.get("CLICKHOUSE_HOST")
load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ["CLICKHOUSE_HOST"] = _ch_host or "localhost"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("import-maps-timeline")


def main() -> int:
    from ingestion.google.maps.parser import parse_archive
    from ingestion.google.maps.insert import insert_visits, insert_paths

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the Timeline ZIP or extracted directory.")
    args = parser.parse_args()

    if not args.path.exists():
        log.error("Path not found: %s", args.path)
        return 1

    with tempfile.TemporaryDirectory(prefix="maps-import-") as tmp:
        root = Path(tmp)
        if args.path.is_file() and zipfile.is_zipfile(args.path):
            with zipfile.ZipFile(args.path) as zf:
                zf.extractall(root)
            log.info("Unzipped %s into %s", args.path, root)
        else:
            root = args.path

        visits, paths = parse_archive(root)

    log.info("Parsed %d visits, %d activity segments — inserting into bronze…", len(visits), len(paths))
    n_visits = insert_visits(visits)
    n_paths = insert_paths(paths)
    log.info("Wrote %d visits, %d paths to bronze.", n_visits, n_paths)
    log.info("Re-run silver.maps_trips segmentation: materialize maps_trip_segmentation in Dagster.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
