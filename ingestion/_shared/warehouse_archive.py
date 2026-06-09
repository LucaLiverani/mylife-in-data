"""Warehouse -> R2 cold archive: nightly Parquet snapshots + restore.

Snapshot layout (one self-contained directory per day):

    archive/warehouse/dt=YYYY-MM-DD/<database>.<table>.parquet
    archive/warehouse/dt=YYYY-MM-DD/_MANIFEST.json

Coverage: every bronze storage table (raw events, enumerated live from
system.tables) plus the DDL-owned silver state tables that are NOT derivable
from bronze (SILVER_STATE_TABLES below). Everything else in silver/gold is a
dbt view rebuilt by `dbt build`. Deliberately excluded: silver.maps_trips
(plain MergeTree, TRUNCATE+INSERT rebuilt by the maps_trips job; an additive
restore would duplicate rows) and the auth database (OAuth secrets do not
belong in the archive; recover by re-auth).

ClickHouse generates the Parquet itself (SELECT ... FORMAT Parquet, zstd), so
no pyarrow/pandas dependency is needed; the bytes travel to R2 through the
existing boto3 helpers, buffered whole in memory. That is MB-scale at this
volume; if a table ever outgrows worker memory, switch to client.raw_stream()
plus a streaming upload helper (r2.download_file is the streaming precedent).
ReplacingMergeTree tables are read with FINAL so a snapshot never carries
pre-merge duplicates. The manifest is uploaded last and marks the snapshot
complete: an interrupted run leaves a dt prefix without one, and restore
skips it when picking the latest.

Restore is an INSERT, never a TRUNCATE: every archived table is
ReplacingMergeTree on a natural key, so restoring over live rows dedups for
free.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .clickhouse import get_client
from .r2 import delete_keys, download_bytes, list_keys, upload_bytes


log = logging.getLogger(__name__)

ARCHIVE_PREFIX = "archive/warehouse"
MANIFEST_FILENAME = "_MANIFEST.json"

# Silver state that exists only in the warehouse: app-mutable, operator-set,
# or LLM-produced. Everything else in silver is a dbt view over bronze.
SILVER_STATE_TABLES = (
    "maps_trip_labels",          # owner confirm/reject labels (dashboard-written)
    "maps_home_locations",       # operator-set home anchors
    "maps_trips_enriched",       # LLM trip verdicts (costly + non-deterministic to re-derive)
    "maps_trip_weather",         # per-trip weather lookups
    "maps_private_places",       # privacy exclusion filter (a restore gap would leak to gold)
    "calendar_category_aliases", # operator-set calendar groupings
)

_DT_RE = re.compile(rf"^{re.escape(ARCHIVE_PREFIX)}/dt=(\d{{4}}-\d{{2}}-\d{{2}})/")

# ClickHouse-side Parquet output: zstd compresses the cold copy well, and
# string-as-string keeps text columns UTF-8 for any external Parquet reader.
_PARQUET_OUT_SETTINGS = {
    "output_format_parquet_compression_method": "zstd",
    "output_format_parquet_string_as_string": 1,
}


def list_archive_tables(client=None) -> list[tuple[str, str, str]]:
    """(database, name, engine) for every table the snapshot covers.

    Bronze is enumerated live, excluding the Kafka-engine consumer table (a
    direct SELECT would steal messages from its materialized view) plus views
    and Null tables, which hold no data. Silver is the explicit state-table
    allowlist; a missing allowlisted table is skipped with a warning so the
    snapshot still works on a warehouse that predates it.
    """
    client = client or get_client()
    bronze = client.query(
        "SELECT name, engine FROM system.tables "
        "WHERE database = 'bronze' "
        "  AND engine NOT LIKE '%Kafka%' "
        "  AND engine NOT IN ('MaterializedView', 'View', 'Null') "
        "ORDER BY name"
    ).result_rows
    tables = [("bronze", name, engine) for name, engine in bronze]

    allowlist = ", ".join(f"'{name}'" for name in SILVER_STATE_TABLES)
    silver = dict(
        client.query(
            "SELECT name, engine FROM system.tables "
            f"WHERE database = 'silver' AND name IN ({allowlist})"
        ).result_rows
    )
    for name in SILVER_STATE_TABLES:
        if name in silver:
            tables.append(("silver", name, silver[name]))
        else:
            log.warning("silver.%s not found on this warehouse; skipping", name)
    return tables


def snapshot_warehouse_to_r2(day: date | None = None) -> dict[str, dict[str, int]]:
    """Dump every covered table to R2 Parquet under one dt= prefix.

    Re-running for the same day overwrites the same keys (idempotent). Returns
    a per-table summary: {"db.table": {"rows": n, "bytes": n}}.
    """
    day = day or datetime.now(tz=timezone.utc).date()
    prefix = f"{ARCHIVE_PREFIX}/dt={day.isoformat()}/"
    client = get_client()

    tables = list_archive_tables(client)
    if not tables:
        raise RuntimeError("no archivable tables found; is the DDL applied?")

    summary: dict[str, dict[str, int]] = {}
    for db, name, engine in tables:
        final = " FINAL" if "Replacing" in engine else ""
        source = f"{db}.`{name}`{final}"
        # Counted in a separate query from the dump (no cross-query snapshot
        # isolation), so tables receiving streaming inserts can drift by a few
        # rows. Advisory only; restore never reads the counts.
        n_rows = client.query(f"SELECT count() FROM {source}").result_rows[0][0]
        data = client.raw_query(
            f"SELECT * FROM {source}", fmt="Parquet", settings=_PARQUET_OUT_SETTINGS
        )
        key = f"{prefix}{db}.{name}.parquet"
        upload_bytes(key, data, content_type="application/vnd.apache.parquet")
        summary[f"{db}.{name}"] = {"rows": int(n_rows), "bytes": len(data)}
        log.info("Archived %s.%s: %d rows, %d bytes -> %s", db, name, n_rows, len(data), key)

    manifest = {
        "dt": day.isoformat(),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "tables": summary,
    }
    upload_bytes(
        f"{prefix}{MANIFEST_FILENAME}",
        json.dumps(manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    return summary


def prune_old_snapshots(retention_days: int, *, today: date | None = None) -> dict[str, int]:
    """Delete dt= prefixes older than the retention window. <= 0 disables."""
    if retention_days <= 0:
        return {"snapshots_deleted": 0, "objects_deleted": 0}
    today = today or datetime.now(tz=timezone.utc).date()
    cutoff = today - timedelta(days=retention_days)

    doomed: list[str] = []
    days: set[str] = set()
    for key in list_keys(f"{ARCHIVE_PREFIX}/dt="):
        m = _DT_RE.match(key)
        if m and date.fromisoformat(m.group(1)) < cutoff:
            doomed.append(key)
            days.add(m.group(1))
    if doomed:
        delete_keys(doomed)
        log.info(
            "Pruned %d snapshot(s) older than %s (%d object(s))",
            len(days), cutoff.isoformat(), len(doomed),
        )
    return {"snapshots_deleted": len(days), "objects_deleted": len(doomed)}


def list_snapshots() -> list[dict[str, Any]]:
    """Available snapshots, oldest first: [{dt, complete, n_objects}]."""
    by_dt: dict[str, list[str]] = {}
    for key in list_keys(f"{ARCHIVE_PREFIX}/dt="):
        m = _DT_RE.match(key)
        if m:
            by_dt.setdefault(m.group(1), []).append(key)
    return [
        {
            "dt": dt,
            "complete": any(k.endswith("/" + MANIFEST_FILENAME) for k in keys),
            "n_objects": len(keys),
        }
        for dt, keys in sorted(by_dt.items())
    ]


def restore_snapshot(
    dt: str | None = None, tables: list[str] | None = None
) -> dict[str, dict[str, int]]:
    """INSERT a snapshot's Parquet files back into the warehouse.

    dt defaults to the latest complete snapshot (the newest with a manifest).
    Additive and idempotent; nothing is dropped or truncated. Target tables
    must already exist (apply warehouse/ddl first on a fresh warehouse);
    snapshot files for tables absent from the target (e.g. legacy tables that
    current DDL no longer creates) are skipped with a warning. The optional
    tables filter matches bare or db-qualified names; requested tables missing
    from the snapshot raise after everything else restored.
    """
    snapshots = {s["dt"]: s for s in list_snapshots()}
    if dt is None:
        complete = [d for d, s in sorted(snapshots.items()) if s["complete"]]
        if not complete:
            raise RuntimeError("no complete snapshot (with manifest) found in R2")
        dt = complete[-1]
    elif dt not in snapshots:
        raise RuntimeError(f"no snapshot found for dt={dt}")
    elif not snapshots[dt]["complete"]:
        log.warning(
            "snapshot dt=%s has no %s (interrupted run?); restoring its partial table set",
            dt, MANIFEST_FILENAME,
        )

    client = get_client()
    existing = {
        f"{db}.{name}"
        for db, name in client.query(
            "SELECT database, name FROM system.tables WHERE database IN ('bronze', 'silver')"
        ).result_rows
    }

    requested = set(tables or [])
    matched: set[str] = set()
    restored: dict[str, dict[str, int]] = {}
    for key in list_keys(f"{ARCHIVE_PREFIX}/dt={dt}/"):
        filename = key.rsplit("/", 1)[-1]
        if not filename.endswith(".parquet"):
            continue
        qualified = filename[: -len(".parquet")]
        db, _, table = qualified.partition(".")
        if not table:
            log.warning("Skipping %s: filename is not <database>.<table>.parquet", key)
            continue
        if requested and not (requested & {qualified, table}):
            continue
        matched.update(requested & {qualified, table})
        if qualified not in existing:
            log.warning(
                "Skipping %s: %s does not exist on this warehouse "
                "(snapshot table absent from current DDL?)", key, qualified,
            )
            continue
        data = download_bytes(key)
        client.raw_insert(f"{db}.`{table}`", insert_block=data, fmt="Parquet")
        restored[qualified] = {"bytes": len(data)}
        log.info("Restored %s from %s (%d bytes)", qualified, key, len(data))

    missing = sorted(requested - matched)
    if missing:
        raise RuntimeError(f"table(s) not found in snapshot dt={dt}: {', '.join(missing)}")
    if not restored:
        raise RuntimeError(f"snapshot dt={dt} contains no restorable tables")
    return restored
