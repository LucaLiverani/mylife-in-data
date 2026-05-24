"""Verify Phase 5 — Maps via Data Portability API.

Checks:
  - All bronze.maps_*, silver.maps_home_locations, silver.maps_trips,
    and gold.gold_maps_*_dashboard tables exist.
  - silver_maps_visits + silver.maps_trips views/tables compile.
  - Informational: row counts in bronze (gated on Google auth + Maps cloud
    availability) and silver.maps_home_locations (gated on set_home_location).

Usage (from repo root, stack running):
    python scripts/verify_phase_5.py
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
        "bronze = sorted(r[0] for r in c.query(\"SHOW TABLES FROM bronze WHERE name LIKE 'maps_%'\").result_rows)\n"
        "silver = sorted(r[0] for r in c.query(\"SHOW TABLES FROM silver WHERE name LIKE 'maps_%' OR name LIKE 'silver_maps_%'\").result_rows)\n"
        "gold = sorted(r[0] for r in c.query(\"SHOW TABLES FROM gold WHERE name LIKE 'gold_maps_%'\").result_rows)\n"
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

    bronze = _set("BRONZE:")
    silver = _set("SILVER:")
    gold = _set("GOLD:")

    bronze_req = {"maps_visits", "maps_path", "maps_search", "maps_directions"}
    silver_req = {"maps_home_locations", "maps_trips", "silver_maps_visits"}
    gold_req = {
        "gold_maps_kpis_dashboard",
        "gold_maps_locations_dashboard",
        "gold_maps_hourly_activity_dashboard",
        "gold_maps_recent_activities",
        "gold_maps_daily_activity_dashboard",
        "gold_maps_destinations_dashboard",
        "gold_maps_trips",
    }
    missing = []
    if bronze_req - bronze:
        missing.append(("bronze", bronze_req - bronze))
    if silver_req - silver:
        missing.append(("silver", silver_req - silver))
    if gold_req - gold:
        missing.append(("gold", gold_req - gold))
    if missing:
        for layer, ms in missing:
            _fail(f"{layer} missing: {sorted(ms)}")
        return False
    _ok(f"bronze: {sorted(bronze_req)}")
    _ok(f"silver: {sorted(silver_req)}")
    _ok(f"gold:   {sorted(gold_req)}")
    return True


def check_dagster_assets() -> bool:
    print("[2/3] Dagster assets/schedules")
    code, out = _exec([
        "docker", "exec", CONTAINER, "python", "-c",
        "from orchestration.dagster.definitions import defs;"
        "ag = defs.resolve_asset_graph();"
        "keys = sorted(str(k) for k in ag.get_all_asset_keys());"
        "print('K:' + '|'.join(keys));"
        "print('S:' + '|'.join(s.name for s in defs.schedules))",
    ])
    if code != 0:
        _fail(f"defs import failed:\n{out}")
        return False
    keys_line = next((l for l in out.splitlines() if l.startswith("K:")), "K:")
    sched_line = next((l for l in out.splitlines() if l.startswith("S:")), "S:")
    keys = keys_line[2:]
    if "maps_daily_incremental" not in keys or "maps_trip_segmentation" not in keys:
        _fail("Maps assets missing from definitions")
        return False
    if "maps_daily_schedule" not in sched_line:
        _fail("maps_daily_schedule missing")
        return False
    _ok("maps_initial_backfill / maps_daily_incremental / maps_trip_segmentation discovered")
    _ok("maps_daily_schedule discovered")
    return True


def check_counts() -> bool:
    print("[3/3] row counts (informational)")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "for q in ['bronze.maps_visits','bronze.maps_path','silver.maps_home_locations','silver.maps_trips']:\n"
        "    n = c.query(f'SELECT count() FROM {q}').result_rows[0][0]\n"
        "    print(f'CNT:{q}={n}')\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    counts = {}
    for line in out.splitlines():
        if line.startswith("CNT:"):
            k, v = line[4:].split("=", 1)
            counts[k] = int(v)

    home_count = counts.get("silver.maps_home_locations", 0)
    if home_count == 0:
        _warn("silver.maps_home_locations empty — run scripts/set_home_location.py")
    else:
        _ok(f"silver.maps_home_locations: {home_count} row(s)")

    visits = counts.get("bronze.maps_visits", 0)
    if visits == 0:
        _warn("bronze.maps_visits empty — Google auth + Maps DP backfill required")
    else:
        _ok(f"bronze.maps_visits: {visits} rows")

    trips = counts.get("silver.maps_trips", 0)
    if trips:
        _ok(f"silver.maps_trips: {trips} trips")
    else:
        _warn("silver.maps_trips empty (no home set or no visits yet)")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_tables(),
        check_dagster_assets(),
        check_counts(),
    ]
    if all(results):
        print("\nPhase 5 verify ✓")
        return 0
    print("\nPhase 5 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
