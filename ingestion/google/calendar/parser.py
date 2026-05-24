"""Parse Google Calendar API Event JSON → bronze.calendar_events row."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_ts(value: dict[str, Any] | None) -> datetime | None:
    if not value:
        return None
    raw = value.get("dateTime") or value.get("date")
    if not raw:
        return None
    if "T" not in raw:
        # All-day events use "date" (YYYY-MM-DD); promote to midnight UTC.
        raw = f"{raw}T00:00:00+00:00"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def event_to_row(event: dict[str, Any], *, calendar_id: str, calendar_name: str) -> dict[str, Any] | None:
    started = _parse_ts(event.get("start"))
    ended = _parse_ts(event.get("end"))
    if not started or not ended:
        return None

    attendees = event.get("attendees") or []
    return {
        "event_id": event.get("id") or "",
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "started_at": started,
        "ended_at": ended,
        "title": event.get("summary") or "",
        "description": event.get("description") or "",
        "location": event.get("location") or "",
        "status": event.get("status") or "confirmed",
        "attendee_count": len(attendees),
        "recurrence_id": event.get("recurringEventId") or "",
    }
