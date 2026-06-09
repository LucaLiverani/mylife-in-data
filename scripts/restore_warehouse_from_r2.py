"""Restore warehouse tables from an R2 Parquet snapshot.

The nightly `warehouse_r2_archive` Dagster job snapshots every bronze storage
table plus the non-derivable silver state tables to R2
(archive/warehouse/dt=YYYY-MM-DD/<database>.<table>.parquet, manifest written
last). This script INSERTs a snapshot back. Additive and idempotent: every
archived table is ReplacingMergeTree on a natural key, so restoring over live
data dedups and nothing is dropped or truncated.

On a fresh warehouse, apply the DDL first (warehouse/ddl/apply.sh) so the
target tables exist, then restore, then run `dbt build` (or wait for the
09:00 UTC build) to refresh the silver/gold views. Not covered by the
snapshot: auth.* (re-auth Google + Spotify) and silver.maps_trips (rebuilt by
the maps_trips job at 09:30 UTC).

Usage (from repo root, with .venv active):
    .venv/bin/python scripts/restore_warehouse_from_r2.py --list
    .venv/bin/python scripts/restore_warehouse_from_r2.py                   # latest complete snapshot
    .venv/bin/python scripts/restore_warehouse_from_r2.py --dt 2026-06-09
    .venv/bin/python scripts/restore_warehouse_from_r2.py --table spotify_plays_raw --table silver.maps_trip_labels

Or inside the running stack:
    docker exec dagster-webserver python /opt/dagster/repo/scripts/restore_warehouse_from_r2.py --list
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
log = logging.getLogger("restore-warehouse-from-r2")


def main() -> int:
    from ingestion._shared.warehouse_archive import list_snapshots, restore_snapshot

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="List available snapshots and exit.")
    parser.add_argument(
        "--dt", help="Snapshot date (YYYY-MM-DD). Default: latest complete snapshot."
    )
    parser.add_argument(
        "--table",
        action="append",
        dest="tables",
        help="Restore only this table, bare or db-qualified (repeatable). "
        "Default: every table in the snapshot.",
    )
    args = parser.parse_args()

    if args.list:
        snapshots = list_snapshots()
        if not snapshots:
            log.info(
                "No snapshots found under archive/warehouse/ in r2://%s",
                os.environ.get("R2_BUCKET"),
            )
            return 0
        for s in snapshots:
            status = "complete" if s["complete"] else "INCOMPLETE (no manifest)"
            log.info("dt=%s  %d object(s)  %s", s["dt"], s["n_objects"], status)
        return 0

    restored = restore_snapshot(dt=args.dt, tables=args.tables)
    log.info("Restored %d table(s): %s", len(restored), ", ".join(sorted(restored)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
