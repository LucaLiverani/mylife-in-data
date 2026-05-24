"""Verify Maps Timeline is still in the cloud (post-2024 migration).

Initiates a 7-day Data Portability archive for Maps scopes, downloads it,
reports row counts. If counts are zero, your Maps history is now on-device
only — fall back to scripts/import_maps_timeline_export.py for manual periodic
exports from the phone.

Usage (after Phase 4 bootstrap):
    .venv/bin/python scripts/probe_maps_data_portability.py
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("probe-maps-dp")


def main() -> int:
    from ingestion._shared.google_oauth import GoogleCredentials
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.parser import parse_archive
    from orchestration.dagster.assets.google import MAPS_RESOURCES

    try:
        creds = GoogleCredentials.load_and_refresh()
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    client = DataPortabilityClient(creds)
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=7)
    log.info("Probing Maps DP for window %s → %s", start.date(), end.date())

    try:
        job_id = client.initiate_archive(MAPS_RESOURCES, start_time=start, end_time=end)
        job = client.wait_for_archive(job_id, timeout_s=900)
    except Exception as exc:
        log.error("DP archive failed: %s", exc)
        return 2

    with tempfile.TemporaryDirectory(prefix="maps-probe-") as tmp:
        root = Path(tmp)
        client.download_archive(job, root)
        visits, paths = parse_archive(root)

    log.info("Result: %d visits, %d activity segments in the last 7 days", len(visits), len(paths))
    if not visits and not paths:
        log.warning(
            "Empty result — Maps Timeline may now be on-device only. "
            "Fall back to scripts/import_maps_timeline_export.py."
        )
        return 3
    log.info("Cloud Timeline is alive — daily incremental schedule should work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
