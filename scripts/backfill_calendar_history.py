"""Backfill full Google Calendar history via the API.

Calendar is the one source that needs no export: events.list with no syncToken
and no timeMin returns every event a calendar holds, so this pulls the full
history for every calendar you own into bronze.calendar_events — the same
table and parser the live push pipeline (calendar_sync_drain) writes to.

Idempotent: bronze.calendar_events is ReplacingMergeTree on (event_id,
started_at), so this is safe to re-run and safe alongside the live pipeline. It
does NOT read or write sync tokens, so the push pipeline keeps working
unchanged (this is a pure read + insert).

Auth: reads the 'standard' Google token from auth.google_tokens. Run on the VM
(where tokens + ClickHouse are canonical), or on the laptop after
`scripts/sync_tokens_from_vm.sh`.

Usage:
    .venv/bin/python scripts/backfill_calendar_history.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-calendar")


def main() -> int:
    from ingestion._shared.google_oauth import GoogleCredentials
    from ingestion.google.calendar.client import CalendarClient
    from ingestion.google.calendar.parser import event_to_row
    from ingestion.google.calendar.insert import insert_events

    try:
        creds = GoogleCredentials.load_and_refresh(scope_group="standard")
    except Exception as exc:
        log.error("Could not load Google 'standard' credentials: %s", exc)
        log.error("Run this on the VM, or `scripts/sync_tokens_from_vm.sh` first on the laptop.")
        return 1

    client = CalendarClient(creds)
    calendars = client.list_calendars()
    log.info("Found %d calendars", len(calendars))

    total = 0
    for cal in calendars:
        calendar_id = cal.get("id") or ""
        calendar_name = cal.get("summaryOverride") or cal.get("summary") or calendar_id
        if not calendar_id:
            continue
        try:
            # sync_token=None -> full pull (all events, no time window), exactly
            # like the live pipeline's first sync. singleEvents=False keeps
            # recurrence masters, matching the stored schema.
            events, _ = client.events_list(calendar_id, sync_token=None)
        except Exception as exc:
            log.warning("events.list failed for %s (%s): %s", calendar_name, calendar_id, exc)
            continue
        rows = [event_to_row(e, calendar_id=calendar_id, calendar_name=calendar_name) for e in events]
        rows = [r for r in rows if r is not None]
        n = insert_events(rows) if rows else 0
        total += n
        log.info("  %-40s %5d events (%d raw)", calendar_name[:40], n, len(events))

    log.info("Backfilled %d calendar events into bronze.calendar_events", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
