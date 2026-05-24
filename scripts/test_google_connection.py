"""Round-trip a Google API connection check.

Verifies BOTH scope groups in `auth.google_tokens`:
  - 'standard'    — userinfo, calendar, youtube.readonly
  - 'portability' — dataportability.* (Maps + YouTube history)

Each row has its own refresh token (Google enforces the split). The probe
exercises both — Calendar/YouTube calls go through 'standard', and the DP
scope check verifies 'portability' has the right scopes granted (no live
archive — that takes minutes and burns quota).

Usage (from repo root, with .venv active):
    .venv/bin/python scripts/test_google_connection.py

Or inside the running stack:
    docker exec dagster-webserver python /opt/dagster/repo/scripts/test_google_connection.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / "infrastructure" / ".env")
except ImportError:
    pass

if not os.path.exists("/.dockerenv"):
    os.environ["CLICKHOUSE_HOST"] = "localhost"


REQUIRED_ENV = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI")

EXPECTED_STANDARD_SCOPES = {
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
}

EXPECTED_PORTABILITY_SCOPES = {
    "https://www.googleapis.com/auth/dataportability.myactivity.youtube",
    "https://www.googleapis.com/auth/dataportability.myactivity.maps",
    "https://www.googleapis.com/auth/dataportability.maps.aliased_places",
    "https://www.googleapis.com/auth/dataportability.maps.starred_places",
}


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _warn(msg: str) -> None:
    print(f"  ! {msg}")


def _fail(msg: str, *, hint: str | None = None) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)
    if hint:
        print(f"    → {hint}", file=sys.stderr)


def check_env() -> bool:
    print("[1/8] env vars")
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        _fail(
            f"missing in env: {missing}",
            hint="fill GOOGLE_CLIENT_* in infrastructure/.env",
        )
        return False
    _ok(
        f"GOOGLE_CLIENT_ID set; redirect_uri={os.environ['GOOGLE_REDIRECT_URI']}; "
        f"account_email={os.environ.get('GOOGLE_ACCOUNT_EMAIL', '<unset>')}"
    )
    return True


def check_token_rows():
    print("[2/8] auth.google_tokens rows (one per scope_group)")
    try:
        from ingestion._shared.clickhouse import get_client
    except ImportError as e:
        _fail(f"can't import ClickHouse helper: {e}")
        return False, set()

    try:
        client = get_client()
        rows = client.query(
            "SELECT account_email, scope_group, length(refresh_token), "
            "length(access_token), issued_at, expires_at "
            "FROM auth.google_tokens FINAL ORDER BY scope_group"
        ).result_rows
    except Exception as exc:
        _fail(
            f"ClickHouse query failed: {str(exc)[:200]}",
            hint="is the stack up? `docker ps` should show clickhouse healthy",
        )
        return False, set()

    if not rows:
        _fail(
            "auth.google_tokens is empty",
            hint="run `.venv/bin/python scripts/bootstrap_google_auth.py` first",
        )
        return False, set()

    have_groups: set[str] = set()
    for email, group, refresh_len, access_len, issued, expires in rows:
        _ok(
            f"{group:12s}: account={email}; "
            f"refresh={refresh_len}c; access={access_len}c; "
            f"issued={issued}; expires={expires}"
        )
        have_groups.add(group)

    missing_groups = {"standard", "portability"} - have_groups
    if missing_groups:
        _warn(
            f"missing scope_group rows: {sorted(missing_groups)} — "
            f"run `bootstrap_google_auth.py --scope-group {sorted(missing_groups)[0]}`"
        )
    return True, have_groups


def check_refresh(scope_group: str, step: str):
    print(f"[{step}] GoogleCredentials.load_and_refresh(scope_group={scope_group!r})")
    try:
        from ingestion._shared.google_oauth import GoogleCredentials

        creds = GoogleCredentials.load_and_refresh(scope_group=scope_group)
    except Exception as exc:
        msg = str(exc)
        hint = None
        if "invalid_grant" in msg:
            hint = (
                "refresh_token rejected — token revoked, expired, or "
                "client_id/secret mismatch. Re-run bootstrap for this group."
            )
        elif "No Google tokens" in msg:
            hint = f"no row for scope_group={scope_group!r} — run bootstrap with --scope-group {scope_group}"
        _fail(f"refresh failed: {msg[:200]}", hint=hint)
        return None
    _ok(f"access_token refreshed (first 10 chars: {creds.token[:10]}…)")
    return creds


def check_scopes(creds, expected: set[str], label: str, step: str) -> bool:
    print(f"[{step}] tokeninfo — {label} scopes granted")
    import requests

    try:
        resp = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": creds.token},
            timeout=15,
        )
    except Exception as exc:
        _fail(f"tokeninfo HTTP failed: {exc}")
        return False
    if not resp.ok:
        _fail(f"tokeninfo returned {resp.status_code}: {resp.text[:200]}")
        return False
    granted = set((resp.json().get("scope") or "").split())
    missing = expected - granted
    if missing:
        _warn(f"NOT granted: {sorted(missing)} — those APIs will 403")
        return False
    _ok(f"all {len(expected)} {label} scopes granted")
    return True


def check_calendar(creds, step: str) -> bool:
    print(f"[{step}] Calendar API — calendarList.list")
    try:
        from googleapiclient.discovery import build

        svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        items = (svc.calendarList().list(maxResults=10).execute().get("items") or [])
    except Exception as exc:
        _fail(f"calendarList failed: {str(exc)[:200]}")
        return False
    _ok(f"{len(items)} calendar(s)")
    for cal in items[:5]:
        _ok(f"  - {cal.get('summary', '?')}")
    return True


def check_youtube(creds, step: str) -> bool:
    print(f"[{step}] YouTube Data API v3 — channels.list(mine=True)")
    try:
        from googleapiclient.discovery import build

        svc = build("youtube", "v3", credentials=creds, cache_discovery=False)
        items = (svc.channels().list(mine=True, part="snippet,statistics").execute().get("items") or [])
    except Exception as exc:
        msg = str(exc)
        if "quotaExceeded" in msg:
            _warn("daily quota exhausted — resets midnight Pacific")
            return True
        _fail(f"channels.list failed: {msg[:200]}")
        return False
    if not items:
        _warn("no YouTube channel for this account — auth still valid")
        return True
    for ch in items[:3]:
        snippet = ch.get("snippet") or {}
        stats = ch.get("statistics") or {}
        _ok(f"  {snippet.get('title', '?')} ({stats.get('subscriberCount', '?')} subs)")
    return True


def main() -> int:
    from datetime import datetime, timezone

    print(f"Google connection probe @ {datetime.now(tz=timezone.utc).isoformat(timespec='seconds')}")

    if not check_env():
        return 1

    ok, have_groups = check_token_rows()
    if not ok:
        return 2

    all_green = True

    if "standard" in have_groups:
        creds_std = check_refresh("standard", "3/8")
        if creds_std is None:
            all_green = False
        else:
            if not check_scopes(creds_std, EXPECTED_STANDARD_SCOPES, "standard", "4/8"):
                all_green = False
            if not check_calendar(creds_std, "5/8"):
                all_green = False
            if not check_youtube(creds_std, "6/8"):
                all_green = False
    else:
        _warn("skipping [3-6/8] — no 'standard' token row")
        all_green = False

    if "portability" in have_groups:
        creds_dp = check_refresh("portability", "7/8")
        if creds_dp is None:
            all_green = False
        else:
            if not check_scopes(creds_dp, EXPECTED_PORTABILITY_SCOPES, "portability", "8/8"):
                all_green = False
    else:
        _warn("skipping [7-8/8] — no 'portability' token row")
        all_green = False

    print()
    if all_green:
        print("Google connection ✓")
        return 0
    print("Google connection ✗ — see warnings above", file=sys.stderr)
    return 4


if __name__ == "__main__":
    sys.exit(main())
