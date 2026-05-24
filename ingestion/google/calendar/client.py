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

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


log = logging.getLogger(__name__)


@dataclass
class WatchSubscription:
    channel_id: str
    resource_id: str
    expiration: datetime
    calendar_id: str


class CalendarClient:
    def __init__(self, creds):
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_calendars(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {}
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._svc.calendarList().list(**kwargs).execute()
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
                resp = self._svc.events().list(**kwargs).execute()
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
        resp = self._svc.events().watch(calendarId=calendar_id, body=body).execute()
        expiration_ms = int(resp.get("expiration") or 0)
        return WatchSubscription(
            channel_id=channel_id,
            resource_id=resp.get("resourceId") or "",
            expiration=datetime.fromtimestamp(expiration_ms / 1000, tz=timezone.utc),
            calendar_id=calendar_id,
        )

    def channels_stop(self, channel_id: str, resource_id: str) -> None:
        try:
            self._svc.channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute()
        except HttpError as exc:
            log.warning("channels.stop %s/%s failed (%s) — leaving to expire naturally", channel_id, resource_id, exc)
