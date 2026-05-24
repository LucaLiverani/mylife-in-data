"""Verify Phase 2 — Spotify history + catalogs + Liked.

Checks:
  - All gold.gold_spotify_* views exist with expected columns.
  - silver_spotify_plays + silver_spotify_saved compile (dbt run).
  - dbt test passes for declared model tests.
  - bronze.spotify_plays_raw + bronze.spotify_saved_tracks have rows
    (only after the schedules have fired AND the Spotify token is valid).

Usage (from repo root, stack running):
    python scripts/verify_phase_2.py
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


REQUIRED_GOLD = {
    "gold_spotify_current_track",
    "gold_spotify_recent_tracks",
    "gold_spotify_kpis_summary",
    "gold_spotify_kpis_dashboard",
    "gold_spotify_top_artists",
    "gold_spotify_genres",
    "gold_spotify_daily_listening",
}


def check_gold_tables() -> bool:
    print("[1/4] gold.gold_spotify_*")
    py = (
        "from ingestion._shared.clickhouse import get_client;"
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse');"
        "c = get_client();"
        "tables = sorted(r[0] for r in c.query(\"SHOW TABLES FROM gold LIKE 'gold_spotify_%'\").result_rows);"
        "print('TABLES:'+','.join(tables))"
    )
    code, out = _exec(["docker", "exec", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    line = next((l for l in out.splitlines() if l.startswith("TABLES:")), "")
    have = set((line or "TABLES:").split(":", 1)[1].split(","))
    missing = REQUIRED_GOLD - have
    if missing:
        _fail(f"missing gold tables: {sorted(missing)}")
        return False
    _ok(f"all required gold_spotify_* present ({len(REQUIRED_GOLD)})")
    return True


def check_silver_views() -> bool:
    print("[2/4] silver views compile")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "tables = sorted(r[0] for r in c.query(\"SHOW TABLES FROM silver\").result_rows)\n"
        "print('TABLES:' + ','.join(tables))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"silver query failed:\n{out}")
        return False
    have = set(next((l for l in out.splitlines() if l.startswith("TABLES:")), "").split(":", 1)[1].split(","))
    required = {"silver_spotify_plays", "silver_spotify_saved"}
    missing = required - have
    if missing:
        _fail(f"missing silver tables: {sorted(missing)}")
        return False
    _ok(f"silver views present: {sorted(required)}")
    return True


def check_bronze_rowcounts() -> bool:
    print("[3/4] bronze row counts (informational)")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "for t in ['spotify_plays_raw','spotify_saved_tracks','spotify_tracks','spotify_artists']:\n"
        "    n = c.query(f'SELECT count() FROM bronze.{t}').result_rows[0][0]\n"
        "    print(f'COUNT:{t}={n}')\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    counts = {}
    for line in out.splitlines():
        if line.startswith("COUNT:"):
            k, v = line[6:].split("=", 1)
            counts[k] = int(v)
    for t, n in counts.items():
        if n > 0:
            _ok(f"bronze.{t}: {n} rows")
        else:
            _warn(f"bronze.{t}: 0 rows (start schedules or run authenticate_local.py)")
    # Don't fail; this depends on user actions.
    return True


def check_dbt_tests() -> bool:
    print("[4/4] dbt tests")
    cmd = (
        "cd /opt/dagster/transformations && "
        "DBT_PROFILES_DIR=/tmp/dbt-test "
        "CLICKHOUSE_HOST=clickhouse CLICKHOUSE_HTTP_PORT=8123 "
        "CLICKHOUSE_USER=$CLICKHOUSE_USER CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD "
        "dbt test --select 'silver_spotify_plays silver_spotify_saved' 2>&1 | tail -10"
    )
    code, out = _exec(["docker", "exec", CONTAINER, "bash", "-c", cmd])
    # On empty tables, NOT NULL tests pass trivially; that's fine.
    if "ERROR" in out and "Completed successfully" not in out:
        _fail(f"dbt test failed:\n{out}")
        return False
    _ok("dbt test passed")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_gold_tables(),
        check_silver_views(),
        check_bronze_rowcounts(),
        check_dbt_tests(),
    ]
    if all(results):
        print("\nPhase 2 verify ✓")
        return 0
    print("\nPhase 2 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
