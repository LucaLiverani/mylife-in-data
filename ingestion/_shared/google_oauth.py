"""Google OAuth credentials wrapper backed by auth.google_tokens in ClickHouse.

The 7-day refresh-token rule (Google Testing app + non-public scopes) means we
expect tokens to be re-issued weekly via the Pages re-auth flow. This module
just loads whatever is in the table, refreshes the access_token in-process via
google-auth, and writes back rotated tokens so future runs use the latest.

Bootstrap path: scripts/bootstrap_google_auth.py performs the local OAuth
flow on http://127.0.0.1:8000/callback and INSERTs the initial row.

Steady-state path: Pages Function /api/_internal/google-auth-callback writes
new tokens after each user re-auth click.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from .clickhouse import get_client, insert_rows

TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass
class GoogleCredentials:
    """Thin wrapper around google.oauth2.credentials.Credentials."""

    account_email: str
    refresh_token: str
    access_token: str
    expires_at: datetime
    scopes: list[str] = field(default_factory=list)
    issued_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # ── load / persist ─────────────────────────────────────────────────────
    @classmethod
    def load_from_clickhouse(cls, account_email: str | None = None) -> "GoogleCredentials":
        """Read latest row from auth.google_tokens. If account_email is None,
        pick the first row found."""

        client = get_client()
        where = "WHERE account_email = %(email)s" if account_email else ""
        params = {"email": account_email} if account_email else None
        rows = client.query(
            f"""
            SELECT account_email, refresh_token, access_token, expires_at, scopes, issued_at
            FROM auth.google_tokens FINAL
            {where}
            ORDER BY _updated_at DESC
            LIMIT 1
            """,
            parameters=params,
        ).result_rows
        if not rows:
            raise RuntimeError(
                "No Google tokens in auth.google_tokens. "
                "Run scripts/bootstrap_google_auth.py on your laptop first."
            )
        email, refresh, access, expires, scopes, issued = rows[0]
        return cls(
            account_email=email,
            refresh_token=refresh,
            access_token=access,
            expires_at=expires if isinstance(expires, datetime) else datetime.fromisoformat(str(expires)),
            scopes=list(scopes or []),
            issued_at=issued if isinstance(issued, datetime) else datetime.fromisoformat(str(issued)),
        )

    def persist_to_clickhouse(self) -> None:
        insert_rows(
            "google_tokens",
            [
                {
                    "account_email": self.account_email,
                    "refresh_token": self.refresh_token,
                    "access_token": self.access_token,
                    "expires_at": self.expires_at,
                    "scopes": self.scopes,
                    "issued_at": self.issued_at,
                }
            ],
            database="auth",
            column_names=["account_email", "refresh_token", "access_token", "expires_at", "scopes", "issued_at"],
        )

    # ── google-auth bridging ───────────────────────────────────────────────
    def to_google_credentials(self) -> Credentials:
        client_id = os.environ["GOOGLE_CLIENT_ID"]
        client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.scopes,
        )

    @classmethod
    def load_and_refresh(cls, account_email: str | None = None) -> Credentials:
        """Convenience used by GoogleAuthResource — load + refresh + persist.

        Returns a `google.oauth2.credentials.Credentials` ready for any
        googleapiclient.discovery client."""

        wrapped = cls.load_from_clickhouse(account_email)
        creds = wrapped.to_google_credentials()

        now = datetime.now(tz=timezone.utc)
        # Refresh if access_token expired or expires in <2 minutes.
        if creds.expired or wrapped.expires_at <= now + timedelta(minutes=2):
            creds.refresh(GoogleRequest())
            # Persist rotated tokens — Google sometimes issues a fresh
            # refresh_token on refresh; capture whichever we got back.
            wrapped.access_token = creds.token
            wrapped.refresh_token = creds.refresh_token or wrapped.refresh_token
            if creds.expiry:
                wrapped.expires_at = creds.expiry.replace(tzinfo=timezone.utc)
            else:
                wrapped.expires_at = now + timedelta(hours=1)
            wrapped.persist_to_clickhouse()

        return creds
