"""Warehouse -> R2 cold-archive asset.

Nightly snapshot to R2 as Parquet (archive/warehouse/dt=YYYY-MM-DD/), then
retention pruning. Covers every bronze storage table (raw events) plus the
DDL-owned silver state tables that are not derivable from bronze (owner trip
labels, home anchors, LLM trip verdicts, weather, the private-places filter,
calendar aliases); dbt views are rebuilt by `dbt build`, and auth.* (OAuth
secrets) is deliberately not archived. Restore via
scripts/restore_warehouse_from_r2.py. R2 stays a side store; nothing in the
live pipeline reads it.
"""

from __future__ import annotations

import os

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    ScheduleDefinition,
    asset,
    define_asset_job,
)


def _retention_days() -> int:
    return int(os.environ.get("R2_ARCHIVE_RETENTION_DAYS") or 30)


@asset(
    group_name="archive",
    description="Snapshot bronze + non-derivable silver state to R2 as Parquet (replayable cold copy), then prune old snapshots.",
)
def warehouse_r2_archive(context) -> dict:
    from ingestion._shared.warehouse_archive import prune_old_snapshots, snapshot_warehouse_to_r2

    summary = snapshot_warehouse_to_r2()
    pruned = prune_old_snapshots(_retention_days())
    context.log.info(
        "Archived %d table(s): %d row(s), %d byte(s); pruned %d old snapshot(s)",
        len(summary),
        sum(t["rows"] for t in summary.values()),
        sum(t["bytes"] for t in summary.values()),
        pruned["snapshots_deleted"],
    )
    return {"tables": summary, "pruned": pruned}


warehouse_r2_archive_job = define_asset_job(
    "warehouse_r2_archive_job",
    selection=AssetSelection.assets(warehouse_r2_archive),
)


warehouse_r2_archive_schedule = ScheduleDefinition(
    job=warehouse_r2_archive_job,
    cron_schedule="30 5 * * *",
    name="warehouse_r2_archive_schedule",
    description="Daily 05:30 UTC warehouse snapshot to R2 (after the 04:00 DP ingest window).",
    default_status=DefaultScheduleStatus.RUNNING,
)
