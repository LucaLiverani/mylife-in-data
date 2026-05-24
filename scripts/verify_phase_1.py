"""Verify Phase 1 — Spotify currently-playing pipeline.

Checks (in order):
  1. Producer container `spotify-current-producer` is Up.
  2. `bronze.spotify_player_current` has at least one row.
  3. `gold.gold_spotify_current_track` returns a row with the expected columns.

The producer's first publish only happens when something is playing in Spotify;
if the dashboard tile shows "no track" the bronze table will be empty even when
the pipeline is healthy. Run the check while a track is playing.

Usage (from repo root, stack running):
    python scripts/verify_phase_1.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys


CONTAINER_PRODUCER = "spotify-current-producer"
CONTAINER_CH = "dagster-webserver"


def _exec(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


def check_producer_up() -> bool:
    print("[1/3] Producer container")
    if shutil.which("docker") is None:
        _fail("docker CLI not on PATH")
        return False
    code, out = _exec(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_PRODUCER])
    if code != 0:
        _fail(f"container '{CONTAINER_PRODUCER}' not present")
        return False
    if "true" not in out.lower():
        _fail(f"container '{CONTAINER_PRODUCER}' not running")
        return False
    _ok(f"{CONTAINER_PRODUCER} Up")
    return True


def check_bronze_rowcount() -> bool:
    print("[2/3] bronze.spotify_player_current")
    py = (
        "from ingestion._shared.clickhouse import get_client;"
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse');"
        "c = get_client();"
        "n = c.query('SELECT count() FROM bronze.spotify_player_current').result_rows[0][0];"
        "print('COUNT:'+str(n))"
    )
    code, out = _exec(["docker", "exec", CONTAINER_CH, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    n = int(out.strip().split(":", 1)[1])
    if n == 0:
        _fail("bronze table is empty — start playback on Spotify and re-run")
        return False
    _ok(f"{n} rows in bronze.spotify_player_current")
    return True


def check_gold_view() -> bool:
    print("[3/3] gold.gold_spotify_current_track")
    py = (
        "from ingestion._shared.clickhouse import get_client;"
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse');"
        "c = get_client();"
        "rows = c.query('SELECT * FROM gold.gold_spotify_current_track').result_rows;"
        "cols = c.query('DESC gold.gold_spotify_current_track').result_rows;"
        "print('COLS:' + ','.join(r[0] for r in cols));"
        "print('NROW:' + str(len(rows)))"
    )
    code, out = _exec(["docker", "exec", CONTAINER_CH, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    cols_line = next((line for line in out.splitlines() if line.startswith("COLS:")), "")
    rows_line = next((line for line in out.splitlines() if line.startswith("NROW:")), "")
    cols = set((cols_line or "").split(":", 1)[1].split(","))
    nrow = int((rows_line or "NROW:0").split(":", 1)[1])

    # Match dashboard/functions/api/spotify/current.ts ClickHouseTrackRow.
    required = {
        "captured_at", "track_id", "track_name", "track_uri",
        "album_id", "album_name", "album_uri", "album_images",
        "artist_id", "artist_name", "artist_uri",
        "artists_ids", "artists_names",
        "is_playing", "progress_ms", "track_duration_ms",
        "device_id", "device_name", "device_type", "device_volume_percent",
        "context_type", "context_uri",
    }
    missing = required - cols
    if missing:
        _fail(f"missing columns: {sorted(missing)}")
        return False
    _ok("column set matches handler's ClickHouseTrackRow")

    if nrow == 0:
        _fail("view returned 0 rows — bronze must have data first")
        return False
    _ok(f"view returned {nrow} row(s)")
    return True


def main() -> int:
    results = [
        check_producer_up(),
        check_bronze_rowcount(),
        check_gold_view(),
    ]
    if all(results):
        print("\nPhase 1 verify ✓")
        return 0
    print("\nPhase 1 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
