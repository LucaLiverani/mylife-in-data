"""Google OAuth credentials wrapper backed by auth.google_tokens in ClickHouse.

Google enforces a hard split: Data Portability scopes (`dataportability.*`)
can only be requested in an OAuth flow that requests nothing else. We run
two separate OAuth flows and store two rows per account, distinguished by
`scope_group`:

  'standard'    — openid, userinfo.{email,profile}, calendar.*, youtube.readonly
  'portability' — dataportability.* only

Each asset / resource picks the row it needs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from .clickhouse import get_client, insert_rows

TOKEN_URI = "https://oauth2.googleapis.com/token"


SCOPE_GROUPS: dict[str, list[str]] = {
    "standard": [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar.events.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/youtube.readonly",
    ],
    "portability": [
        "https://www.googleapis.com/auth/dataportability.myactivity.youtube",
        "https://www.googleapis.com/auth/dataportability.myactivity.maps",
        "https://www.googleapis.com/auth/dataportability.maps.aliased_places",
        "https://www.googleapis.com/auth/dataportability.maps.starred_places",
    ],
}


@dataclass
class GoogleCredentials:
    """Thin wrapper around google.oauth2.credentials.Credentials."""

    account_email: str
    scope_group: str
    refresh_token: str
    access_token: str
    expires_at: datetime
    scopes: list[str] = field(default_factory=list)
    issued_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @classmethod
    def load_from_clickhouse(
        cls,
        account_email: str | None = None,
        *,
        scope_group: str = "standard",
    ) -> "GoogleCredentials":
        """Read latest row for (account_email, scope_group)."""

        client = get_client()
        where_parts = ["scope_group = %(group)s"]
        params: dict = {"group": scope_group}
        if account_email:
            where_parts.append("account_email = %(email)s")
            params["email"] = account_email
        where = " AND ".join(where_parts)
        rows = client.query(
            f"""
            SELECT account_email, scope_group, refresh_token, access_token,
                   expires_at, scopes, issued_at
            FROM auth.google_tokens FINAL
            WHERE {where}
            ORDER BY _updated_at DESC
            LIMIT 1
            """,
            parameters=params,
        ).result_rows
        if not rows:
            raise RuntimeError(
                f"No Google tokens for scope_group={scope_group!r} in auth.google_tokens. "
                f"Run `python scripts/bootstrap_google_auth.py --scope-group {scope_group}` "
                "on your laptop first."
            )
        email, group, refresh, access, expires, scopes, issued = rows[0]

        def _to_utc(value) -> datetime:
            # ClickHouse DateTime → tz-naive Python datetime. Treat as UTC.
            dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        return cls(
            account_email=email,
            scope_group=group,
            refresh_token=refresh,
            access_token=access,
            expires_at=_to_utc(expires),
            scopes=list(scopes or []),
            issued_at=_to_utc(issued),
        )

    def persist_to_clickhouse(self) -> None:
        insert_rows(
            "google_tokens",
            [
                {
                    "account_email": self.account_email,
                    "scope_group": self.scope_group,
                    "refresh_token": self.refresh_token,
                    "access_token": self.access_token,
                    "expires_at": self.expires_at,
                    "scopes": self.scopes,
                    "issued_at": self.issued_at,
                }
            ],
            database="auth",
            column_names=[
                "account_email", "scope_group", "refresh_token", "access_token",
                "expires_at", "scopes", "issued_at",
            ],
        )

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
    def load_and_refresh(
        cls,
        account_email: str | None = None,
        *,
        scope_group: str = "standard",
    ) -> Credentials:
        """Load + refresh + persist rotated tokens. Returns a ready-to-use
        `google.oauth2.credentials.Credentials`."""

        wrapped = cls.load_from_clickhouse(account_email, scope_group=scope_group)
        creds = wrapped.to_google_credentials()

        now = datetime.now(tz=timezone.utc)
        if creds.expired or wrapped.expires_at <= now + timedelta(minutes=2):
            creds.refresh(GoogleRequest())
            wrapped.access_token = creds.token
            wrapped.refresh_token = creds.refresh_token or wrapped.refresh_token
            if creds.expiry:
                wrapped.expires_at = creds.expiry.replace(tzinfo=timezone.utc)
            else:
                wrapped.expires_at = now + timedelta(hours=1)
            wrapped.persist_to_clickhouse()

        return creds
