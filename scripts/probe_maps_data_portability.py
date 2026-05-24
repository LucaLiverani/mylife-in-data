"""Verify Maps Timeline is still in the cloud (post-2024 migration).

Initiates a 7-day Data Portability archive for Maps scopes, downloads it,
reports row counts. If counts are zero, your Maps history is now on-device
only — fall back to scripts/import_maps_timeline_export.py for manual periodic
exports from the phone.

Uses the 'portability' scope group from auth.google_tokens (the DP credentials
seeded by `bootstrap_google_auth.py --scope-group portability`).

Usage:
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

# Host runs need to hit localhost for ClickHouse (the .env holds the
# in-container hostname `clickhouse`).
if not os.path.exists("/.dockerenv"):
    os.environ["CLICKHOUSE_HOST"] = "localhost"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("probe-maps-dp")

# Data Portability `resources` are short names (NOT full scope URLs).
# Format follows the dotted suffix of the scope URL, e.g.:
#   scope:    https://www.googleapis.com/auth/dataportability.maps.aliased_places
#   resource: maps.aliased_places
MAPS_RESOURCES = [
    "myactivity.maps",
    "maps.aliased_places",
    "maps.starred_places",
]


def main() -> int:
    from ingestion._shared.google_oauth import GoogleCredentials
    from ingestion.google.portability import DataPortabilityClient
    from ingestion.google.maps.parser import parse_archive

    try:
        creds = GoogleCredentials.load_and_refresh(scope_group="portability")
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    client = DataPortabilityClient(creds)
    log.info("Probing Maps DP (full snapshot — saved-places resources don't support time windows)")

    # If we passed --job-id, skip initiate and re-fetch state for that job
    # (signed URLs are still valid for ~1h after archive completion).
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", default=None, help="Re-use an existing archive job_id instead of initiating a new one")
    args = parser.parse_args()

    job_id = args.job_id
    if not job_id:
        try:
            job_id = client.initiate_archive(MAPS_RESOURCES)
        except RuntimeError as exc:
            # Google 409s with the existing job_id when the same resources were
            # exported in the last 24h. Parse it out and re-use that job.
            msg = str(exc)
            import re

            m = re.search(r"job ([a-f0-9-]{36})", msg)
            if m:
                job_id = m.group(1)
                log.info("Reusing existing archive job %s (24h rate-limit hit)", job_id)
            else:
                log.error("DP archive failed: %s", exc)
                return 2
        except Exception as exc:
            log.error("DP archive failed: %s", exc)
            return 2

    try:
        job = client.wait_for_archive(job_id, timeout_s=900)
    except Exception as exc:
        log.error("wait_for_archive failed: %s", exc)
        return 2

    # NOTE: not using a TemporaryDirectory so the archive sticks around for
    # inspection after the probe exits. Path is logged below.
    import tempfile as _tempfile
    root = Path(_tempfile.mkdtemp(prefix="maps-probe-"))
    client.download_archive(job, root)

    # Survey what's in the archive — file names, sizes, first ~200 chars of
    # each JSON file. This tells us the shape so we can write the right parser.
    log.info("Archive extracted to %s", root)
    log.info("─── Files found ───")
    json_files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            size = path.stat().st_size
            rel = path.relative_to(root)
            log.info("  %s  (%d bytes)", rel, size)
            if path.suffix.lower() == ".json":
                json_files.append(path)
    log.info("─── JSON top-level shape ───")
    for jf in json_files[:10]:
        try:
            head = jf.read_text(encoding="utf-8")[:200]
            log.info("  %s → %s", jf.relative_to(root), head.replace("\n", " "))
        except Exception as exc:
            log.info("  %s → unreadable (%s)", jf.relative_to(root), exc)

    visits, paths = parse_archive(root)
    log.info("Result: %d visits, %d activity segments parsed by current parser", len(visits), len(paths))
    if not visits and not paths:
        log.warning(
            "Empty result — either Maps Timeline is now on-device only, "
            "or the granted DP scopes (aliased_places + starred_places) don't "
            "cover Timeline data. Try adding dataportability.myactivity.maps "
            "to the portability scope group, or fall back to "
            "scripts/import_maps_timeline_export.py."
        )
        return 3
    log.info("Cloud Timeline is alive — daily incremental schedule should work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
