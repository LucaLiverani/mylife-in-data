"""One-time Google OAuth bootstrap (laptop only).

Runs the OAuth consent flow on http://127.0.0.1:8000/callback, swaps the code
for refresh+access tokens, and INSERTs them into auth.google_tokens.

Usage (from repo root, with .venv active, ClickHouse reachable on localhost):
    .venv/bin/python scripts/bootstrap_google_auth.py

Required env (from infrastructure/.env — auto-loaded):
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    CLICKHOUSE_USER, CLICKHOUSE_PASSWORD
    GOOGLE_ACCOUNT_EMAIL (used as the row key)

After this completes, the Pages re-auth flow takes over for weekly renewals.
"""

from __future__ import annotations

import http.server
import logging
import os
import socketserver
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bootstrap-google-auth")

# Same scope list as the Pages Function (dashboard/functions/_shared/google-auth.ts).
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/dataportability.youtube.watch_history",
    "https://www.googleapis.com/auth/dataportability.youtube.search_history",
    "https://www.googleapis.com/auth/dataportability.maps.aliased_places",
    "https://www.googleapis.com/auth/dataportability.maps.starred_places",
]

REDIRECT_URI = "http://127.0.0.1:8000/callback"
PORT = 8000


def _check_env() -> None:
    missing = [k for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET") if not os.environ.get(k)]
    if missing:
        log.error("Missing env vars: %s — set them in infrastructure/.env first.", missing)
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
        code = qs.get("code", [None])[0]
        error = qs.get("error", [None])[0]
        _CallbackHandler.code = code
        _CallbackHandler.error = error
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "Auth code received. You can close this tab." if code else f"Auth failed: {error}"
        self.wfile.write(f"<html><body><h1>{msg}</h1></body></html>".encode("utf-8"))

    def log_message(self, *_a, **_kw):  # silence default logger
        return


def _await_callback() -> str:
    handler = _CallbackHandler
    handler.code = None
    handler.error = None
    server = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    log.info("Listening on %s …", REDIRECT_URI)
    Thread(target=server.serve_forever, daemon=True).start()
    while handler.code is None and handler.error is None:
        pass
    server.shutdown()
    server.server_close()
    if handler.error:
        log.error("Google returned: %s", handler.error)
        sys.exit(1)
    return handler.code  # type: ignore[return-value]


def _exchange_code(code: str) -> dict:
    import requests

    body = {
        "code": code,
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = requests.post("https://oauth2.googleapis.com/token", data=body, timeout=30)
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

    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        import json

        return json.loads(decoded).get("email", "") or ""
    except Exception:
        return ""


def _persist(tokens: dict) -> str:
    # Force the script to talk to ClickHouse via localhost (host stack).
    os.environ.setdefault("CLICKHOUSE_HOST", "localhost")

    from ingestion._shared.clickhouse import insert_rows

    account_email = (
        _email_from_id_token(tokens.get("id_token"))
        or os.environ.get("GOOGLE_ACCOUNT_EMAIL")
        or "unknown@unknown"
    )
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600) - 30))
    scopes = (tokens.get("scope") or " ".join(SCOPES)).split()

    insert_rows(
        "google_tokens",
        [
            {
                "account_email": account_email,
                "refresh_token": tokens.get("refresh_token", ""),
                "access_token": tokens.get("access_token", ""),
                "expires_at": expires_at,
                "scopes": scopes,
                "issued_at": datetime.now(tz=timezone.utc),
            }
        ],
        database="auth",
        column_names=["account_email", "refresh_token", "access_token", "expires_at", "scopes", "issued_at"],
    )
    return account_email


def main() -> int:
    _check_env()

    params = urllib.parse.urlencode(
        {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(SCOPES),
        }
    )
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    print("Open this URL in your browser to authorize:")
    print("\n  " + auth_url + "\n")

    try:
        import webbrowser

        webbrowser.open(auth_url)
    except Exception:
        pass

    code = _await_callback()
    log.info("Got auth code — exchanging for tokens…")
    tokens = _exchange_code(code)

    if not tokens.get("refresh_token"):
        log.warning(
            "No refresh_token in response — Google only issues it on the first "
            "consent for this user. Revoke the app at "
            "https://myaccount.google.com/permissions and re-run."
        )

    log.info("Writing tokens to auth.google_tokens…")
    email = _persist(tokens)
    log.info("Bootstrap complete for %s. Next re-auth via the Pages flow.", email)
    return 0


if __name__ == "__main__":
    sys.exit(main())
