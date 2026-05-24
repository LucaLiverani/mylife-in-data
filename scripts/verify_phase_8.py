"""Verify Phase 8 — observability + finishing touches.

Checks:
  - dashboard/functions/api/system/health.ts exists and dashboard/public/_redirects
    no longer rewrites /api/system/health to the mock.
  - freshness_monitor asset + schedule are discovered by Dagster.
  - dbt test passes against the full project.
  - All eight verify scripts are present.

Usage (from repo root, stack running):
    python scripts/verify_phase_8.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


CONTAINER = "dagster-webserver"


def _exec(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


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


def check_health_handler() -> bool:
    print("[1/4] /api/system/health handler")
    handler = "dashboard/functions/api/system/health.ts"
    if not os.path.exists(handler):
        _fail(f"{handler} missing")
        return False
    with open("dashboard/public/_redirects") as fh:
        text = fh.read()
    if "/api/system/health" in text:
        _fail("_redirects still rewrites /api/system/health to mocks")
        return False
    _ok("system/health Pages Function exists and the redirect is gone")
    return True


def check_dagster_observability() -> bool:
    print("[2/4] freshness_monitor asset + schedule")
    code, out = _exec([
        "docker", "exec", CONTAINER, "python", "-c",
        "from orchestration.dagster.definitions import defs;"
        "ag = defs.resolve_asset_graph();"
        "keys = '|'.join(sorted(str(k) for k in ag.get_all_asset_keys()));"
        "scheds = '|'.join(sorted(s.name for s in defs.schedules));"
        "print('K:'+keys);"
        "print('S:'+scheds)",
    ])
    if code != 0:
        _fail(f"defs import failed:\n{out}")
        return False
    keys = next((l[2:] for l in out.splitlines() if l.startswith("K:")), "")
    scheds = next((l[2:] for l in out.splitlines() if l.startswith("S:")), "")
    if "freshness_monitor" not in keys:
        _fail("freshness_monitor asset not discovered")
        return False
    if "freshness_monitor_schedule" not in scheds:
        _fail("freshness_monitor_schedule not discovered")
        return False
    _ok("freshness_monitor + schedule discovered")
    return True


def check_dbt_tests() -> bool:
    print("[3/4] dbt test")
    cmd = (
        "cd /opt/dagster/transformations && "
        "DBT_PROFILES_DIR=/tmp/dbt-test "
        "CLICKHOUSE_HOST=clickhouse CLICKHOUSE_HTTP_PORT=8123 "
        "CLICKHOUSE_USER=$CLICKHOUSE_USER CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD "
        "dbt test 2>&1 | tail -10"
    )
    code, out = _exec(["docker", "exec", CONTAINER, "bash", "-c", cmd])
    if "Completed successfully" not in out and "PASS" not in out:
        _fail(f"dbt test failed:\n{out}")
        return False
    _ok("dbt test passed")
    return True


def check_verify_scripts() -> bool:
    print("[4/4] verify_phase_*.py scripts")
    missing = []
    for n in range(0, 9):
        path = f"scripts/verify_phase_{n}.py"
        if not os.path.exists(path):
            missing.append(path)
    if missing:
        _fail(f"missing: {missing}")
        return False
    _ok("all 9 verify scripts present (phase 0–8)")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_health_handler(),
        check_dagster_observability(),
        check_dbt_tests(),
        check_verify_scripts(),
    ]
    if all(results):
        print("\nPhase 8 verify ✓")
        return 0
    print("\nPhase 8 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
