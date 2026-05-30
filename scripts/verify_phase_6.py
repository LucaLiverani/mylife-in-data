"""Verify Phase 6 — YouTube DP + Data API v3 enrichment.

Checks:
  - All bronze.youtube_* and gold.gold_youtube_*_dashboard tables exist.
  - silver_youtube_watches / silver_youtube_searches views compile.
  - Dagster discovers the youtube_history_daily / enricher assets +
    youtube_daily_schedule + youtube_metadata_enricher_sensor.

Usage (from repo root, stack running):
    python scripts/verify_phase_6.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys


CONTAINER = "dagster-webserver"


def _exec(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _warn(msg: str) -> None:
    print(f"  ! {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


def require_docker() -> bool:
    if shutil.which("docker") is None:
        _fail("docker CLI not on PATH")
        return False
    code, _ = _exec(["docker", "inspect", CONTAINER])
    if code != 0:
        _fail(f"{CONTAINER} not running")
        return False
    return True


def check_tables() -> bool:
    print("[1/3] table presence")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "bronze = sorted(r[0] for r in c.query(\"SHOW TABLES FROM bronze WHERE name LIKE 'youtube_%'\").result_rows)\n"
        "silver = sorted(r[0] for r in c.query(\"SHOW TABLES FROM silver WHERE name LIKE 'silver_youtube_%'\").result_rows)\n"
        "gold = sorted(r[0] for r in c.query(\"SHOW TABLES FROM gold WHERE name LIKE 'gold_youtube_%'\").result_rows)\n"
        "print('BRONZE:'+','.join(bronze))\n"
        "print('SILVER:'+','.join(silver))\n"
        "print('GOLD:'+','.join(gold))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False

    def _set(prefix: str) -> set[str]:
        line = next((l for l in out.splitlines() if l.startswith(prefix)), "")
        return set((line or prefix).split(":", 1)[1].split(","))

    bronze, silver, gold = _set("BRONZE:"), _set("SILVER:"), _set("GOLD:")
    bronze_req = {"youtube_watch_history", "youtube_search_history", "youtube_videos", "youtube_channels"}
    silver_req = {"silver_youtube_watches", "silver_youtube_searches"}
    gold_req = {
        "gold_youtube_kpis_with_watch_time_dashboard",
        "gold_youtube_top_channels_dashboard",
        "gold_youtube_category_breakdown_dashboard",
        "gold_youtube_daily_watch_time_breakdown_dashboard",
        "gold_youtube_recent_videos_dashboard",
        "gold_youtube_hourly_activity_dashboard",
    }

    failures = []
    if bronze_req - bronze:
        failures.append(("bronze", bronze_req - bronze))
    if silver_req - silver:
        failures.append(("silver", silver_req - silver))
    if gold_req - gold:
        failures.append(("gold", gold_req - gold))
    if failures:
        for layer, ms in failures:
            _fail(f"{layer} missing: {sorted(ms)}")
        return False
    _ok(f"bronze: {sorted(bronze_req)}")
    _ok(f"silver: {sorted(silver_req)}")
    _ok(f"gold:   {len(gold_req)} tables present")
    return True


def check_dagster() -> bool:
    print("[2/3] Dagster discovery")
    code, out = _exec([
        "docker", "exec", CONTAINER, "python", "-c",
        "from orchestration.dagster.definitions import defs;"
        "ag = defs.resolve_asset_graph();"
        "keys = '|'.join(sorted(str(k) for k in ag.get_all_asset_keys()));"
        "scheds = '|'.join(sorted(s.name for s in defs.schedules));"
        "sens = '|'.join(sorted(s.name for s in defs.sensors));"
        "print('K:'+keys);"
        "print('S:'+scheds);"
        "print('SEN:'+sens)",
    ])
    if code != 0:
        _fail(f"defs import failed:\n{out}")
        return False
    keys = next((l[2:] for l in out.splitlines() if l.startswith("K:")), "")
    scheds = next((l[2:] for l in out.splitlines() if l.startswith("S:")), "")
    sens = next((l[4:] for l in out.splitlines() if l.startswith("SEN:")), "")
    # YouTube daily ingest is now the combined Maps+YouTube DP asset
    # (maps_youtube_dp_daily) on the unified google_dp_daily_schedule.
    needed_keys = ["maps_youtube_dp_daily", "youtube_metadata_enricher", "youtube_schema"]
    for k in needed_keys:
        if k not in keys:
            _fail(f"missing Dagster asset: {k}")
            return False
    if "google_dp_daily_schedule" not in scheds:
        _fail("missing google_dp_daily_schedule")
        return False
    if "youtube_metadata_enricher_sensor" not in sens:
        _fail("missing youtube_metadata_enricher_sensor")
        return False
    _ok("YouTube assets, schedule, and enricher sensor discovered")
    return True


def check_counts() -> bool:
    print("[3/3] row counts (informational)")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "for q in ['bronze.youtube_watch_history','bronze.youtube_videos','bronze.youtube_channels','bronze.youtube_search_history']:\n"
        "    n = c.query(f'SELECT count() FROM {q}').result_rows[0][0]\n"
        "    print(f'CNT:{q}={n}')\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    for line in out.splitlines():
        if line.startswith("CNT:"):
            k, v = line[4:].split("=", 1)
            n = int(v)
            (_ok if n > 0 else _warn)(f"{k}: {n}")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [check_tables(), check_dagster(), check_counts()]
    if all(results):
        print("\nPhase 6 verify ✓")
        return 0
    print("\nPhase 6 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
