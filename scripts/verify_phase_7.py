"""Verify Phase 7 — Calendar push pipeline.

Checks:
  - bronze.calendar_events, bronze.calendar_sync_notifications,
    silver.calendar_category_aliases, auth.calendar_channels all exist.
  - All 7 gold.gold_calendar_* views compile.
  - Pages Function calendar-webhook.ts exists in the source tree.
  - Dagster discovers calendar_channels_setup/renew + calendar_sync_drain +
    calendar_sync_sensor.

Usage (from repo root, stack running):
    python scripts/verify_phase_7.py
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
    print("[1/4] table presence")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "bronze = sorted(r[0] for r in c.query(\"SHOW TABLES FROM bronze WHERE name LIKE 'calendar_%'\").result_rows)\n"
        "silver = sorted(r[0] for r in c.query(\"SHOW TABLES FROM silver WHERE name LIKE 'calendar_%' OR name LIKE 'silver_calendar%'\").result_rows)\n"
        "gold = sorted(r[0] for r in c.query(\"SHOW TABLES FROM gold WHERE name LIKE 'gold_calendar_%'\").result_rows)\n"
        "auth = sorted(r[0] for r in c.query(\"SHOW TABLES FROM auth WHERE name LIKE 'calendar_%'\").result_rows)\n"
        "print('BRONZE:'+','.join(bronze))\n"
        "print('SILVER:'+','.join(silver))\n"
        "print('GOLD:'+','.join(gold))\n"
        "print('AUTH:'+','.join(auth))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False

    def _set(prefix: str) -> set[str]:
        line = next((l for l in out.splitlines() if l.startswith(prefix)), "")
        return set((line or prefix).split(":", 1)[1].split(","))

    bronze, silver, gold, auth = _set("BRONZE:"), _set("SILVER:"), _set("GOLD:"), _set("AUTH:")

    bronze_req = {"calendar_events", "calendar_sync_notifications"}
    silver_req = {"calendar_category_aliases", "silver_calendar_events"}
    gold_req = {
        "gold_calendar_kpis",
        "gold_calendar_busy_hours",
        "gold_calendar_categories",
        "gold_calendar_weekday_breakdown",
        "gold_calendar_daily_events",
        "gold_calendar_week_grid",
        "gold_calendar_upcoming_events",
    }
    auth_req = {"calendar_channels"}

    failures = []
    if bronze_req - bronze:
        failures.append(("bronze", bronze_req - bronze))
    if silver_req - silver:
        failures.append(("silver", silver_req - silver))
    if gold_req - gold:
        failures.append(("gold", gold_req - gold))
    if auth_req - auth:
        failures.append(("auth", auth_req - auth))
    if failures:
        for layer, ms in failures:
            _fail(f"{layer} missing: {sorted(ms)}")
        return False

    _ok(f"bronze: {sorted(bronze_req)}")
    _ok(f"silver: {sorted(silver_req)}")
    _ok(f"gold:   {len(gold_req)} tables present")
    _ok(f"auth:   {sorted(auth_req)}")
    return True


def check_webhook_function() -> bool:
    print("[2/4] Pages webhook function")
    path = "dashboard/functions/api/internal/calendar-webhook.ts"
    if not os.path.exists(path):
        _fail(f"{path} missing")
        return False
    _ok(f"{path} present")
    return True


def check_dagster() -> bool:
    print("[3/4] Dagster discovery")
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
        _fail(f"defs failed:\n{out}")
        return False
    keys = next((l[2:] for l in out.splitlines() if l.startswith("K:")), "")
    scheds = next((l[2:] for l in out.splitlines() if l.startswith("S:")), "")
    sens = next((l[4:] for l in out.splitlines() if l.startswith("SEN:")), "")
    for k in ("calendar_channels_setup", "calendar_channels_renew", "calendar_sync_drain", "calendar_polling_fallback"):
        if k not in keys:
            _fail(f"missing Dagster asset: {k}")
            return False
    if "calendar_renew_schedule" not in scheds:
        _fail("missing calendar_renew_schedule")
        return False
    if "calendar_sync_sensor" not in sens:
        _fail("missing calendar_sync_sensor")
        return False
    _ok("Calendar assets, schedule, and sync sensor discovered")
    return True


def check_redirects_removed() -> bool:
    print("[4/4] mock redirect for /api/google/calendar removed")
    with open("dashboard/public/_redirects") as fh:
        text = fh.read()
    if "/api/google/calendar" in text:
        _warn("_redirects still contains /api/google/calendar — mock fallback still wins over the Pages function")
        return False
    _ok("_redirects clean — /api/google/calendar routes to the new handler")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_tables(),
        check_webhook_function(),
        check_dagster(),
        check_redirects_removed(),
    ]
    if all(results):
        print("\nPhase 7 verify ✓")
        return 0
    print("\nPhase 7 verify ✗", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
