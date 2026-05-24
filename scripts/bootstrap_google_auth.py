"""One-time Google OAuth bootstrap (laptop only).

Google enforces a hard split: Data Portability scopes can't share an OAuth
flow with any other scope. So this script runs TWO OAuth flows in sequence:

  1. 'standard'    — openid, userinfo, calendar, youtube.readonly
  2. 'portability' — dataportability.* only

Each produces its own refresh token, persisted as a separate row in
auth.google_tokens (keyed by `scope_group`). Either flow can be skipped or
re-run independently with `--scope-group {standard|portability}`.

Usage (from repo root, with .venv active, ClickHouse reachable on localhost):
    .venv/bin/python scripts/bootstrap_google_auth.py
    .venv/bin/python scripts/bootstrap_google_auth.py --scope-group standard
    .venv/bin/python scripts/bootstrap_google_auth.py --scope-group portability

Required env (auto-loaded from infrastructure/.env):
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD
    GOOGLE_ACCOUNT_EMAIL (used as the row key)

After both flows complete, the Pages re-auth flow takes over for renewals.
"""

from __future__ import annotations

import argparse
import http.server
import logging
import os
import socketserver
import sys
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")

# Host runs need to hit localhost for ClickHouse (the .env file holds the
# in-container hostname `clickhouse`).
if not os.path.exists("/.dockerenv"):
    os.environ["CLICKHOUSE_HOST"] = "localhost"

from ingestion._shared.google_oauth import SCOPE_GROUPS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bootstrap-google-auth")

REDIRECT_URI = "http://127.0.0.1:8000/callback"
PORT = 8000


def _check_env() -> None:
    missing = [k for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET") if not os.environ.get(k)]
    if missing:
        log.error("Missing env vars: %s — fill them in infrastructure/.env first.", missing)
        sys.exit(1)


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        if url.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(url.query)
        _CallbackHandler.code = qs.get("code", [None])[0]
        _CallbackHandler.error = qs.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "Auth code received. You can close this tab and return to the terminal."
            if _CallbackHandler.code
            else f"Auth failed: {_CallbackHandler.error}"
        )
        self.wfile.write(f"<html><body><h1>{msg}</h1></body></html>".encode("utf-8"))

    def log_message(self, *_a, **_kw):  # silence default access logs
        return


class _ReusableTCPServer(socketserver.TCPServer):
    # SO_REUSEADDR so back-to-back flows don't trip over TIME_WAIT on port 8000.
    allow_reuse_address = True


def _await_callback() -> str:
    _CallbackHandler.code = None
    _CallbackHandler.error = None
    server = _ReusableTCPServer(("127.0.0.1", PORT), _CallbackHandler)
    log.info("Listening on %s …", REDIRECT_URI)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        while _CallbackHandler.code is None and _CallbackHandler.error is None:
            pass
    finally:
        server.shutdown()
        server.server_close()
    if _CallbackHandler.error:
        log.error("Google returned: %s", _CallbackHandler.error)
        sys.exit(1)
    return _CallbackHandler.code  # type: ignore[return-value]


def _exchange_code(code: str) -> dict:
    import requests

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if not resp.ok:
        log.error("Token exchange failed: %s\n%s", resp.status_code, resp.text)
        sys.exit(1)
    return resp.json()


def _email_from_id_token(id_token: str | None) -> str:
    if not id_token:
        return ""
    parts = id_token.split(".")
    if len(parts) != 3:
        return ""
    import base64
    import json

    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded)).get("email", "") or ""
    except Exception:
        return ""


def _persist(tokens: dict, scope_group: str, scopes: list[str]) -> str:
    from ingestion._shared.clickhouse import insert_rows

    account_email = (
        _email_from_id_token(tokens.get("id_token"))
        or os.environ.get("GOOGLE_ACCOUNT_EMAIL")
        or "unknown@unknown"
    )
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600) - 30))

    insert_rows(
        "google_tokens",
        [
            {
                "account_email": account_email,
                "scope_group": scope_group,
                "refresh_token": tokens.get("refresh_token", ""),
                "access_token": tokens.get("access_token", ""),
                "expires_at": expires_at,
                "scopes": scopes,
                "issued_at": datetime.now(tz=timezone.utc),
            }
        ],
        database="auth",
        column_names=[
            "account_email", "scope_group", "refresh_token", "access_token",
            "expires_at", "scopes", "issued_at",
        ],
    )
    return account_email


def run_flow(scope_group: str) -> None:
    scopes = SCOPE_GROUPS[scope_group]
    params = urllib.parse.urlencode(
        {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            # Don't set `include_granted_scopes` — Data Portability scopes
            # reject it ("Incremental auth is not allowed"). Each flow stands
            # alone since prompt=consent forces a fresh grant anyway.
            "scope": " ".join(scopes),
        }
    )
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    print(f"\n── scope group: {scope_group} ({len(scopes)} scopes) ──")
    print("Open this URL in your browser to authorize:\n")
    print(f"  {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    code = _await_callback()
    log.info("Got auth code for %s — exchanging for tokens…", scope_group)
    tokens = _exchange_code(code)

    if not tokens.get("refresh_token"):
        log.warning(
            "No refresh_token in response — Google only issues it on first consent. "
            "If this is a re-run, revoke at https://myaccount.google.com/permissions and retry."
        )

    email = _persist(tokens, scope_group, scopes)
    log.info("✓ scope_group=%s persisted for %s", scope_group, email)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope-group",
        choices=("standard", "portability", "both"),
        default="both",
        help="Which OAuth flow(s) to run. 'both' runs them in sequence (default).",
    )
    args = parser.parse_args()

    _check_env()

    groups = ("standard", "portability") if args.scope_group == "both" else (args.scope_group,)
    for g in groups:
        run_flow(g)

    log.info("Bootstrap complete. Re-auths in steady state happen via the Pages flow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
