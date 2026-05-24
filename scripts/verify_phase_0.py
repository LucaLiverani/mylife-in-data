"""Verify Phase 0 — scaffolding.

Runs checks inside the dagster-webserver container so all dependencies
(clickhouse_connect, dagster, dbt) are available without a host venv.

Checks:
  - ClickHouse reachable; databases bronze/silver/gold/auth present.
  - auth.google_tokens + auth.alerts present.
  - Dagster code location loads (`from orchestration.dagster.definitions import defs`).
  - dbt debug passes from /opt/dagster/transformations.

Usage (from repo root, with the stack running):
    python scripts/verify_phase_0.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
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
        _fail("docker CLI not on PATH — run inside the host with the stack running")
        return False
    code, _ = _exec(["docker", "inspect", CONTAINER])
    if code != 0:
        _fail(f"container '{CONTAINER}' not running — start the stack with infrastructure/start-all.sh")
        return False
    return True


def check_clickhouse() -> bool:
    print("[1/3] ClickHouse")
    py = (
        "from ingestion._shared.clickhouse import get_client;"
        "import os;"
        "os.environ.setdefault('CLICKHOUSE_HOST','clickhouse');"
        "c = get_client();"
        "dbs = sorted(r[0] for r in c.query('SHOW DATABASES').result_rows);"
        "tables = sorted(r[0] for r in c.query('SHOW TABLES FROM auth').result_rows);"
        "print('DBS:'+','.join(dbs));"
        "print('AUTH:'+','.join(tables))"
    )
    code, out = _exec(["docker", "exec", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"ClickHouse query failed:\n{out}")
        return False

    dbs = next((line[4:] for line in out.splitlines() if line.startswith("DBS:")), "").split(",")
    auth = next((line[5:] for line in out.splitlines() if line.startswith("AUTH:")), "").split(",")

    required = {"bronze", "silver", "gold", "auth", "default", "system"}
    missing = required - set(dbs)
    if missing:
        _fail(f"missing databases: {sorted(missing)}")
        return False
    _ok(f"databases present: {sorted(required)}")

    auth_required = {"google_tokens", "alerts"}
    missing_t = auth_required - set(auth)
    if missing_t:
        _fail(f"auth.* missing tables: {sorted(missing_t)}")
        return False
    _ok("auth.google_tokens and auth.alerts present")
    return True


def check_dagster_definitions() -> bool:
    print("[2/3] Dagster code location")
    code, out = _exec(
        [
            "docker", "exec", CONTAINER, "python", "-c",
            "from orchestration.dagster.definitions import defs;"
            "ag = defs.resolve_asset_graph();"
            "print('ASSETS:'+str(len(list(ag.get_all_asset_keys()))))",
        ]
    )
    if code != 0:
        _fail(f"definitions import failed:\n{out}")
        return False
    n_line = next((line for line in out.splitlines() if line.startswith("ASSETS:")), "")
    _ok(f"definitions loaded ({n_line[7:] if n_line else 'unknown'} assets)")
    return True


def check_dbt() -> bool:
    print("[3/3] dbt project")
    cmd = (
        "mkdir -p /tmp/dbt-test && "
        "cp /opt/dagster/transformations/profiles.yml.example /tmp/dbt-test/profiles.yml && "
        "DBT_PROFILES_DIR=/tmp/dbt-test "
        "CLICKHOUSE_HOST=clickhouse CLICKHOUSE_HTTP_PORT=8123 "
        "CLICKHOUSE_USER=$CLICKHOUSE_USER CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD "
        "dbt debug --project-dir /opt/dagster/transformations 2>&1 | tail -3"
    )
    code, out = _exec(["docker", "exec", CONTAINER, "bash", "-c", cmd])
    if "All checks passed" not in out:
        _fail(f"dbt debug failed:\n{out}")
        return False
    _ok("dbt debug passed")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_clickhouse(),
        check_dagster_definitions(),
        check_dbt(),
    ]
    if all(results):
        print("\nPhase 0 verify ✓")
        return 0
    print("\nPhase 0 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
