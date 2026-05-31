"""Import a Google Takeout export: YouTube history + Maps "My Activity".

Takeout is the full-history counterpart to the daily Data Portability ingest —
the DP archive uses the *same* layout, so the same parsers apply. Use this to
backfill years of YouTube watch/search history and Maps activity beyond the
1-year DP backfill, and without spending the per-client 24h DP cooldown.

Request at takeout.google.com:
  - "YouTube and YouTube Music" -> history -> set format to JSON (not HTML)
  - "My Activity" -> Maps -> format JSON
For Maps *Timeline* (location visits/paths) use
scripts/import_maps_timeline_export.py instead — that's a different data shape.

Idempotent: every bronze target is ReplacingMergeTree on a natural key, so
overlap with the live DP ingest dedups automatically.

The source can be a local path or an R2 location (needs R2_* in
infrastructure/.env). A bare prefix pulls every object under it — handy for a
multi-part Takeout split into several zips:
    .venv/bin/python scripts/import_google_takeout.py /path/to/takeout.zip
    .venv/bin/python scripts/import_google_takeout.py /path/to/Takeout/
    .venv/bin/python scripts/import_google_takeout.py r2://google-takeout/        # all parts
    .venv/bin/python scripts/import_google_takeout.py r2://imports/takeout.zip    # one object
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
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
log = logging.getLogger("import-google-takeout")


def main() -> int:
    from ingestion._shared.import_source import open_archive_root
    from ingestion.google.youtube.parser import parse_archive as parse_youtube
    from ingestion.google.youtube.insert import insert_watch_history, insert_search_history
    from ingestion.google.maps.activity_parser import parse_archive_for_activity
    from ingestion.google.maps.insert import insert_activity

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source",
        help="Local path (zip or dir) or R2 location (r2://<key> or r2://<prefix>/).",
    )
    args = parser.parse_args()

    try:
        with open_archive_root(args.source) as root:
            # Same parsers the DP ingest uses (DP archive == Takeout layout).
            watch, search = parse_youtube(root)
            activity = parse_archive_for_activity(root)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1

    n_watch = insert_watch_history(watch)
    n_search = insert_search_history(search)
    n_activity = insert_activity(activity)
    log.info(
        "Imported: youtube_watch=%d, youtube_search=%d, maps_activity=%d",
        n_watch, n_search, n_activity,
    )
    if n_watch == 0 and n_search == 0:
        log.warning(
            "0 YouTube rows parsed — was history exported as JSON? In Takeout: "
            "YouTube and YouTube Music -> 'Multiple formats' -> History = JSON (default is HTML)."
        )
    log.info(
        "Then materialize maps_place_enrichment + youtube_metadata_enricher in Dagster "
        "to enrich the newly imported rows."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
