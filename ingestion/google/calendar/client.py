"""Google Calendar API wrapper. Thin layer around googleapiclient.

Three operations matter:
  - list_calendars(): /calendarList → all subscribed calendars
  - events_list(calendar_id, sync_token=None): /events with optional incremental
  - events_watch(calendar_id, webhook_url, channel_id, token): subscribe
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


log = logging.getLogger(__name__)

# Hard socket timeout for every Calendar API call. Without it a stalled
# events.list() hangs the Dagster step forever — the root cause of the
# 2026-05-30 run-queue wedge. 30s is generous for a single 250-item page.
_HTTP_TIMEOUT_SECONDS = 30

# googleapiclient retries 5xx / 429 and transient socket errors with
# exponential backoff + jitter when num_retries > 0. Calendar's backend throws
# sporadic 503 "Backend Error"s mid-pagination that clear on the next attempt;
# without this a single blip crashes the Dagster op (2026-05-31, calendar_polling_job).
_API_NUM_RETRIES = 5


@dataclass
class WatchSubscription:
    channel_id: str
    resource_id: str
    expiration: datetime
    calendar_id: str


class CalendarClient:
    def __init__(self, creds):
        # build() rejects http= and credentials= together, so carry the creds
        # on an AuthorizedHttp whose underlying transport enforces the timeout.
        authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=_HTTP_TIMEOUT_SECONDS))
        self._svc = build("calendar", "v3", http=authed_http, cache_discovery=False)

    def list_calendars(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {}
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._svc.calendarList().list(**kwargs).execute(num_retries=_API_NUM_RETRIES)
            items.extend(resp.get("items") or [])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return items

    def events_list(
        self,
        calendar_id: str,
        *,
        sync_token: str | None = None,
        page_size: int = 250,
    ) -> tuple[list[dict[str, Any]], str]:
        """Return (events, next_sync_token). Uses syncToken for deltas; falls
        back to a full pull if Google returns 410 GONE (sync token expired)."""

        events: list[dict[str, Any]] = []
        next_token = sync_token
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "calendarId": calendar_id,
                "maxResults": page_size,
                "showDeleted": True,
                "singleEvents": False,
            }
            if next_token:
                kwargs["syncToken"] = next_token
                next_token = None  # syncToken is request-scoped on first call
            if page_token:
                kwargs["pageToken"] = page_token
            try:
                resp = self._svc.events().list(**kwargs).execute(num_retries=_API_NUM_RETRIES)
            except HttpError as exc:
                if exc.resp.status == 410:
                    log.warning("Sync token expired for %s — falling back to full pull", calendar_id)
                    return self.events_list(calendar_id, sync_token=None)
                raise
            events.extend(resp.get("items") or [])
            page_token = resp.get("nextPageToken")
            if not page_token:
                return events, resp.get("nextSyncToken") or ""

    def events_watch(
        self,
        calendar_id: str,
        webhook_url: str,
        token: str,
    ) -> WatchSubscription:
        channel_id = str(uuid.uuid4())
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "token": token,
        }
        resp = self._svc.events().watch(calendarId=calendar_id, body=body).execute(num_retries=_API_NUM_RETRIES)
        expiration_ms = int(resp.get("expiration") or 0)
        return WatchSubscription(
            channel_id=channel_id,
            resource_id=resp.get("resourceId") or "",
            expiration=datetime.fromtimestamp(expiration_ms / 1000, tz=timezone.utc),
            calendar_id=calendar_id,
        )

    def channels_stop(self, channel_id: str, resource_id: str) -> None:
        try:
            self._svc.channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute(num_retries=_API_NUM_RETRIES)
        except HttpError as exc:
            log.warning("channels.stop %s/%s failed (%s) — leaving to expire naturally", channel_id, resource_id, exc)
