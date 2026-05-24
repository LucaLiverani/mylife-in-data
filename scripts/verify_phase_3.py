"""Verify Phase 3 — cross-source events plumbing.

Checks:
  - silver.events_unified storage table exists (Phase 3 DDL).
  - silver.silver_events_unified view exists and unions Spotify projections.
  - gold.gold_home_recent_events, gold_home_overview_stats,
    gold_home_daily_data_generation all exist with expected columns.

Counts will only flip non-zero after Spotify schedules have populated
bronze.spotify_plays_raw / bronze.spotify_saved_tracks (requires Spotify auth).

Usage (from repo root, stack running):
    python scripts/verify_phase_3.py
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


def check_tables_exist() -> bool:
    print("[1/3] silver + gold tables")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "silver = sorted(r[0] for r in c.query(\"SHOW TABLES FROM silver\").result_rows)\n"
        "gold = sorted(r[0] for r in c.query(\"SHOW TABLES FROM gold WHERE name LIKE 'gold_home_%'\").result_rows)\n"
        "print('SILVER:' + ','.join(silver))\n"
        "print('GOLD:' + ','.join(gold))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    silver_line = next((l for l in out.splitlines() if l.startswith("SILVER:")), "")
    gold_line = next((l for l in out.splitlines() if l.startswith("GOLD:")), "")
    silver = set((silver_line or "SILVER:").split(":", 1)[1].split(","))
    gold = set((gold_line or "GOLD:").split(":", 1)[1].split(","))

    silver_required = {
        "events_unified",
        "silver_events_unified",
        "silver_events_unified_spotify_plays",
        "silver_events_unified_spotify_liked",
    }
    gold_required = {
        "gold_home_recent_events",
        "gold_home_overview_stats",
        "gold_home_daily_data_generation",
    }
    missing_silver = silver_required - silver
    missing_gold = gold_required - gold
    if missing_silver:
        _fail(f"missing silver tables: {sorted(missing_silver)}")
        return False
    if missing_gold:
        _fail(f"missing gold tables: {sorted(missing_gold)}")
        return False
    _ok(f"silver: {sorted(silver_required)}")
    _ok(f"gold:   {sorted(gold_required)}")
    return True


def check_overview_stats_shape() -> bool:
    print("[2/3] gold_home_overview_stats columns")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "cols = sorted(r[0] for r in c.query(\"DESC gold.gold_home_overview_stats\").result_rows)\n"
        "print('COLS:' + ','.join(cols))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    line = next((l for l in out.splitlines() if l.startswith("COLS:")), "")
    cols = set((line or "COLS:").split(":", 1)[1].split(","))
    required = {"songsStreamed", "artistsListened", "videosWatched", "youtubeChannels", "searchQueries", "citiesVisited"}
    missing = required - cols
    if missing:
        _fail(f"overview_stats missing cols: {sorted(missing)}")
        return False
    _ok(f"columns match handler: {sorted(required)}")
    return True


def check_event_counts() -> bool:
    print("[3/3] cross-source counts (informational)")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "n1 = c.query('SELECT count() FROM silver.silver_events_unified').result_rows[0][0]\n"
        "n2 = c.query('SELECT count() FROM gold.gold_home_recent_events').result_rows[0][0]\n"
        "spotify = c.query(\"SELECT count() FROM silver.silver_events_unified WHERE source='spotify'\").result_rows[0][0]\n"
        "print(f'EVENTS:{n1}')\n"
        "print(f'GOLD:{n2}')\n"
        "print(f'SPOTIFY:{spotify}')\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    counts = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            try:
                counts[k] = int(v)
            except ValueError:
                pass
    n = counts.get("EVENTS", 0)
    if n == 0:
        _warn("silver_events_unified is empty (Spotify schedules haven't fired or token missing)")
    else:
        _ok(f"silver_events_unified: {n} rows ({counts.get('SPOTIFY', 0)} spotify)")
    _ok(f"gold_home_recent_events: {counts.get('GOLD', 0)} rows")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_tables_exist(),
        check_overview_stats_shape(),
        check_event_counts(),
    ]
    if all(results):
        print("\nPhase 3 verify ✓")
        return 0
    print("\nPhase 3 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
