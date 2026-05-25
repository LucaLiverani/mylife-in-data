"""Verify Phase 4 — Google OAuth foundation.

Checks:
  - auth.google_tokens has at least one row (requires bootstrap_google_auth.py).
  - GoogleAuthResource.load_from_clickhouse() returns valid credentials.
  - /api/internal/google-auth-redirect builds a URL with valid state (smoke
    test — runs the helper directly in node-less mode using a python port of
    the HMAC step is overkill; we just check the env vars are present).
  - Refresh path: if expires_at is in the past, load_and_refresh() succeeds.

Usage (from repo root, stack running):
    python scripts/verify_phase_4.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


CONTAINER = "dagster-webserver"


def _exec(cmd: list[str], env: dict | None = None) -> tuple[int, str]:
    full = {**os.environ, **(env or {})}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=full)
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


def check_token_row_present() -> bool:
    print("[1/3] auth.google_tokens row")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.clickhouse import get_client\n"
        "c = get_client()\n"
        "rows = c.query('SELECT account_email, length(refresh_token), length(access_token), issued_at FROM auth.google_tokens FINAL').result_rows\n"
        "print('ROWS:'+str(len(rows)))\n"
        "for r in rows:\n"
        "    print('TOK:'+str(r))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"query failed:\n{out}")
        return False
    n = int(next((l for l in out.splitlines() if l.startswith("ROWS:")), "ROWS:0")[5:])
    if n == 0:
        _warn("auth.google_tokens is empty — run scripts/bootstrap_google_auth.py to seed.")
        return False
    _ok(f"{n} token row(s) present")
    for line in out.splitlines():
        if line.startswith("TOK:"):
            _ok(line[4:])
    return True


def check_resource_loads() -> bool:
    print("[2/3] GoogleAuthResource.load_and_refresh")
    py = (
        "import os; os.environ.setdefault('CLICKHOUSE_HOST','clickhouse')\n"
        "from ingestion._shared.google_oauth import GoogleCredentials\n"
        "creds = GoogleCredentials.load_and_refresh()\n"
        "print('TOKEN10:' + (creds.token or '')[:10])\n"
        "print('SCOPES:' + str(len(creds.scopes or [])))\n"
    )
    code, out = _exec(["docker", "exec", "-i", CONTAINER, "python", "-c", py])
    if code != 0:
        _fail(f"load_and_refresh failed:\n{out}")
        return False
    tok = next((l for l in out.splitlines() if l.startswith("TOKEN10:")), "TOKEN10:")
    n_scopes = next((l for l in out.splitlines() if l.startswith("SCOPES:")), "SCOPES:0")
    if not tok[8:]:
        _fail("access_token empty after refresh")
        return False
    _ok(f"access_token loads (first 10 chars: {tok[8:]}…)")
    _ok(f"scopes: {n_scopes[7:]}")
    return True


def check_pages_env() -> bool:
    print("[3/3] dashboard/.env.production")
    env_file = "dashboard/.env.production"
    if not os.path.exists(env_file):
        _fail(f"{env_file} not found")
        return False
    with open(env_file) as fh:
        text = fh.read()
    required = ["CALENDAR_WEBHOOK_TOKEN", "GOOGLE_REAUTH_STATE_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"]
    missing = [k for k in required if k not in text]
    if missing:
        _warn(f"{env_file} missing Pages secret keys: {missing}")
        return False
    _ok("all Pages secrets are declared in dashboard/.env.production")
    return True


def main() -> int:
    if not require_docker():
        return 1
    results = [
        check_token_row_present(),
        check_resource_loads(),
        check_pages_env(),
    ]
    if all(results):
        print("\nPhase 4 verify ✓")
        return 0
    print("\nPhase 4 verify ✗ — see warnings above", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
