"""Google Calendar push pipeline.

The Pages Function webhook (`/api/internal/calendar-webhook`) catches
notifications and writes one row to `bronze.calendar_sync_notifications` per
event. This file holds:
  - `calendar_channels_setup` (one-shot): subscribe events.watch on every
    calendar the user has access to. Persists channels in `auth.calendar_channels`.
  - `calendar_channels_renew` (daily): re-watch each calendar before the 7-day
    TTL. Old channels expire naturally.
  - `calendar_sync_sensor` (every 30s): drain unprocessed notifications by
    calling events.list?syncToken=… and INSERTing the delta into bronze.
  - `calendar_polling_fallback` (every 60s, disabled by default): same logic
    minus the webhook trigger, for when the webhook breaks.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    RunRequest,
    ScheduleDefinition,
    SensorEvaluationContext,
    SkipReason,
    asset,
    define_asset_job,
    sensor,
)


REPO_ROOT_IN_CONTAINER = Path("/opt/dagster/repo")


def _ddl_path(filename: str) -> Path:
    p = REPO_ROOT_IN_CONTAINER / "warehouse" / "ddl" / filename
    if p.exists():
        return p
    return Path(__file__).resolve().parents[3] / "warehouse" / "ddl" / filename


def _webhook_url() -> str:
    base = os.environ.get("GOOGLE_REDIRECT_URI", "")
    # GOOGLE_REDIRECT_URI ends with /api/internal/google-auth-callback;
    # swap the leaf for the calendar webhook.
    if not base:
        return ""
    base = base.rstrip("/")
    parent = base.rsplit("/", 1)[0]
    return f"{parent}/calendar-webhook"


@asset(group_name="google", description="DDL bootstrap for Calendar bronze + alias table.")
def calendar_schema(context) -> str:
    from ingestion._shared.clickhouse import execute_file

    execute_file(str(_ddl_path("70_calendar.sql")))
    return "ok"


@asset(
    group_name="google",
    description="Subscribe events.watch for every Calendar the user owns.",
    deps=[calendar_schema],
    required_resource_keys={"google_auth_standard"},
)
def calendar_channels_setup(context) -> dict:
    from ingestion._shared.clickhouse import insert_rows
    from ingestion.google.calendar.client import CalendarClient

    token = os.environ.get("CALENDAR_WEBHOOK_TOKEN")
    if not token:
        raise RuntimeError("CALENDAR_WEBHOOK_TOKEN must be set in env.")
    webhook = _webhook_url()
    if not webhook:
        raise RuntimeError("Cannot derive webhook URL — set GOOGLE_REDIRECT_URI.")

    creds = context.resources.google_auth_standard.get_credentials()
    client = CalendarClient(creds)

    calendars = client.list_calendars()
    rows = []
    for cal in calendars:
        cal_id = cal.get("id") or ""
        cal_name = cal.get("summary") or cal_id
        try:
            sub = client.events_watch(cal_id, webhook, token=token)
        except Exception as exc:
            context.log.warning("events.watch failed for %s: %s", cal_id, exc)
            continue
        rows.append(
            {
                "calendar_id": cal_id,
                "calendar_name": cal_name,
                "channel_id": sub.channel_id,
                "resource_id": sub.resource_id,
                "sync_token": "",
                "expiration": sub.expiration,
            }
        )

    if rows:
        insert_rows(
            "calendar_channels",
            rows,
            database="auth",
            column_names=["calendar_id", "calendar_name", "channel_id", "resource_id", "sync_token", "expiration"],
        )
    context.log.info("Subscribed %d/%d calendars", len(rows), len(calendars))
    return {"calendars": len(calendars), "watched": len(rows)}


@asset(
    group_name="google",
    description="Re-subscribe each Calendar channel before its 7-day TTL expires.",
    deps=[calendar_schema],
    required_resource_keys={"google_auth_standard"},
)
def calendar_channels_renew(context) -> int:
    from ingestion._shared.clickhouse import get_client, insert_rows
    from ingestion.google.calendar.client import CalendarClient

    token = os.environ.get("CALENDAR_WEBHOOK_TOKEN")
    webhook = _webhook_url()
    if not (token and webhook):
        context.log.warning("Missing CALENDAR_WEBHOOK_TOKEN/GOOGLE_REDIRECT_URI — skipping renew.")
        return 0

    client = get_client()
    rows = client.query(
        "SELECT calendar_id, calendar_name FROM auth.calendar_channels FINAL"
    ).result_rows
    if not rows:
        context.log.info("No calendar channels to renew.")
        return 0

    creds = context.resources.google_auth_standard.get_credentials()
    cal_client = CalendarClient(creds)
    renewed = []
    for calendar_id, calendar_name in rows:
        try:
            sub = cal_client.events_watch(calendar_id, webhook, token=token)
            renewed.append(
                {
                    "calendar_id": calendar_id,
                    "calendar_name": calendar_name,
                    "channel_id": sub.channel_id,
                    "resource_id": sub.resource_id,
                    "sync_token": "",
                    "expiration": sub.expiration,
                }
            )
        except Exception as exc:
            context.log.warning("renew failed for %s: %s", calendar_id, exc)
    if renewed:
        insert_rows(
            "calendar_channels",
            renewed,
            database="auth",
            column_names=["calendar_id", "calendar_name", "channel_id", "resource_id", "sync_token", "expiration"],
        )
    context.log.info("Renewed %d/%d channels", len(renewed), len(rows))
    return len(renewed)


@asset(
    group_name="google",
    description="Drain unprocessed sync notifications: fetch delta + INSERT bronze.",
    deps=[calendar_schema],
    required_resource_keys={"google_auth_standard"},
)
def calendar_sync_drain(context) -> dict:
    from ingestion._shared.clickhouse import get_client, insert_rows
    from ingestion.google.calendar.client import CalendarClient
    from ingestion.google.calendar.parser import event_to_row
    from ingestion.google.calendar.insert import insert_events

    client = get_client()

    # Pull unprocessed notifications, joined back to the channel → calendar_id.
    rows = client.query(
        "SELECT n.channel_id, n.calendar_id, n.message_number "
        "FROM bronze.calendar_sync_notifications n "
        "WHERE n.processed_at IS NULL "
        "ORDER BY n.received_at"
    ).result_rows

    if not rows:
        context.log.info("No unprocessed notifications.")
        return {"processed_notifications": 0, "events_inserted": 0}

    # Group by calendar_id to make one events.list call per affected calendar.
    by_cal: dict[str, list[tuple[str, int]]] = {}
    for channel_id, calendar_id, msg_num in rows:
        by_cal.setdefault(calendar_id, []).append((channel_id, msg_num))

    creds = context.resources.google_auth_standard.get_credentials()
    cal_client = CalendarClient(creds)

    n_events = 0
    n_processed = 0
    for calendar_id, notifs in by_cal.items():
        cal_meta = client.query(
            "SELECT calendar_name, sync_token FROM auth.calendar_channels FINAL "
            "WHERE calendar_id = %(c)s LIMIT 1",
            parameters={"c": calendar_id},
        ).result_rows
        if not cal_meta:
            context.log.warning("No channel row for %s — skipping", calendar_id)
            continue
        calendar_name, sync_token = cal_meta[0]
        events, next_token = cal_client.events_list(calendar_id, sync_token=sync_token or None)
        rows_to_insert = [event_to_row(e, calendar_id=calendar_id, calendar_name=calendar_name) for e in events]
        rows_to_insert = [r for r in rows_to_insert if r is not None]
        if rows_to_insert:
            n_events += insert_events(rows_to_insert)

        if next_token:
            insert_rows(
                "calendar_channels",
                [{
                    "calendar_id": calendar_id,
                    "calendar_name": calendar_name,
                    "channel_id": notifs[0][0],
                    "resource_id": "",
                    "sync_token": next_token,
                    "expiration": datetime(1970, 1, 1, tzinfo=timezone.utc),
                }],
                database="auth",
                column_names=["calendar_id", "calendar_name", "channel_id", "resource_id", "sync_token", "expiration"],
            )

        max_msg = max(m for _, m in notifs)
        client.command(
            "ALTER TABLE bronze.calendar_sync_notifications "
            "UPDATE processed_at = now64() "
            "WHERE calendar_id = %(c)s AND message_number <= %(m)s AND processed_at IS NULL",
            parameters={"c": calendar_id, "m": max_msg},
        )
        n_processed += len(notifs)

    return {"processed_notifications": n_processed, "events_inserted": n_events}


@asset(
    group_name="google",
    description="60s polling fallback for Calendar (off by default; enable when webhook breaks).",
    deps=[calendar_schema],
    required_resource_keys={"google_auth_standard"},
)
def calendar_polling_fallback(context) -> dict:
    """Identical to calendar_sync_drain minus the notification check.

    Triggered manually or via the polling schedule below (kept off by default).
    """
    from ingestion._shared.clickhouse import get_client, insert_rows
    from ingestion.google.calendar.client import CalendarClient
    from ingestion.google.calendar.parser import event_to_row
    from ingestion.google.calendar.insert import insert_events

    client = get_client()
    rows = client.query(
        "SELECT calendar_id, calendar_name, sync_token FROM auth.calendar_channels FINAL"
    ).result_rows

    if not rows:
        return {"events_inserted": 0}

    creds = context.resources.google_auth_standard.get_credentials()
    cal_client = CalendarClient(creds)

    inserted = 0
    for calendar_id, calendar_name, sync_token in rows:
        events, next_token = cal_client.events_list(calendar_id, sync_token=sync_token or None)
        rows_to_insert = [event_to_row(e, calendar_id=calendar_id, calendar_name=calendar_name) for e in events]
        rows_to_insert = [r for r in rows_to_insert if r is not None]
        if rows_to_insert:
            inserted += insert_events(rows_to_insert)
        if next_token:
            insert_rows(
                "calendar_channels",
                [{
                    "calendar_id": calendar_id,
                    "calendar_name": calendar_name,
                    "channel_id": "polling",
                    "resource_id": "",
                    "sync_token": next_token,
                    "expiration": datetime(1970, 1, 1, tzinfo=timezone.utc),
                }],
                database="auth",
                column_names=["calendar_id", "calendar_name", "channel_id", "resource_id", "sync_token", "expiration"],
            )
    return {"events_inserted": inserted}


@asset(
    group_name="google",
    description="Geocode distinct Calendar event locations into the shared place catalog (travel corroboration for trips).",
    deps=[calendar_schema],
)
def calendar_place_enrichment(context) -> dict:
    """Walk distinct, non-empty `location` strings in bronze.calendar_events
    that aren't yet in bronze.maps_place_catalog and geocode each one into the
    SAME catalog the Maps pipeline uses (keyed `q:<normalized text>`), so a
    calendar "Zürich" and a Maps "Zürich" share one row. silver_calendar_geo
    joins on that key to flag foreign / far-from-home events; Phase 5's trip
    LLM reads them as corroborating evidence.

    Catalog is monotonic and the lookup is shared with Maps, so this never
    re-fetches a place either pipeline already resolved. Misses + junk
    (virtual-meeting "locations", URLs) are negative-cached and leave the
    worklist. Per-run cap via CALENDAR_ENRICH_LIMIT."""
    import os

    from ingestion._shared.clickhouse import get_client
    from ingestion.google.maps.geocoder import (
        GeocoderConfigError,
        get_geocoder,
        get_or_lookup,
    )

    try:
        geocoder = get_geocoder()
    except GeocoderConfigError as exc:
        context.log.warning("Geocoder not configured (%s) — skipping calendar enrichment", exc)
        return {"looked_up": 0, "skipped": True}

    ch = get_client()
    limit = int(os.environ.get("CALENDAR_ENRICH_LIMIT", "200"))
    # Build the worklist with the EXACT q:<text> key silver_calendar_geo joins
    # on (lowercased, whitespace-collapsed) so the lookup key == the join key.
    rows = ch.query(
        """
        SELECT loc_key, argMax(location, started_at) AS lookup_text
        FROM (
            SELECT
                concat('q:', trimBoth(replaceRegexpAll(lowerUTF8(location), '[[:space:]]+', ' '))) AS loc_key,
                location,
                started_at
            FROM bronze.calendar_events FINAL
            WHERE status != 'cancelled' AND location != ''
        )
        WHERE loc_key NOT IN (SELECT place_id FROM bronze.maps_place_catalog)
        GROUP BY loc_key
        LIMIT %(lim)s
        """,
        parameters={"lim": limit},
    ).result_rows

    looked_up = unresolved = failed = 0
    for loc_key, lookup_text in rows:
        try:
            result = get_or_lookup(
                place_id=loc_key, text=lookup_text or "", geocoder=geocoder, ch=ch
            )
        except Exception as exc:
            context.log.warning("calendar lookup failed for %s (%s): %s", loc_key, lookup_text, exc)
            failed += 1
            continue
        if result is None:
            unresolved += 1
        else:
            looked_up += 1
    context.log.info(
        "Calendar location enrichment via %s: resolved=%d, unresolved=%d, errors=%d (limit %d/run)",
        geocoder.provider, looked_up, unresolved, failed, limit,
    )
    return {"looked_up": looked_up, "unresolved": unresolved, "failed": failed}


# ── Jobs + schedules + sensors ─────────────────────────────────────────────
calendar_renew_job = define_asset_job(
    "calendar_renew_job",
    selection=AssetSelection.assets(calendar_channels_renew),
)


calendar_enrich_job = define_asset_job(
    "calendar_enrich_job",
    selection=AssetSelection.assets(calendar_place_enrichment),
)


calendar_enrich_schedule = ScheduleDefinition(
    job=calendar_enrich_job,
    # 08:30 UTC — after the day's calendar polling has landed events and before
    # the 09:00 dbt build, so silver_calendar_geo sees a warm catalog.
    cron_schedule="30 8 * * *",
    name="calendar_enrich_schedule",
    description="Daily 08:30 UTC — geocode new Calendar event locations into the place catalog.",
    default_status=DefaultScheduleStatus.RUNNING,
)


calendar_renew_schedule = ScheduleDefinition(
    job=calendar_renew_job,
    cron_schedule="0 6 * * *",
    name="calendar_renew_schedule",
    description="Daily 06:00 — re-subscribe each Calendar channel.",
    default_status=DefaultScheduleStatus.RUNNING,
)


calendar_sync_job = define_asset_job(
    "calendar_sync_job",
    selection=AssetSelection.assets(calendar_sync_drain),
)


@sensor(
    job=calendar_sync_job,
    minimum_interval_seconds=30,
    name="calendar_sync_sensor",
    description="Fire when bronze.calendar_sync_notifications has unprocessed rows.",
    default_status=DefaultSensorStatus.RUNNING,
)
def calendar_sync_sensor(context: SensorEvaluationContext):
    from ingestion._shared.clickhouse import get_client

    try:
        client = get_client()
        n = client.query(
            "SELECT count() FROM bronze.calendar_sync_notifications WHERE processed_at IS NULL"
        ).result_rows[0][0]
    except Exception as exc:
        return SkipReason(f"sensor check failed: {exc}")
    if n == 0:
        return SkipReason("no unprocessed notifications")
    return RunRequest(run_key=f"calendar-drain-{n}", tags={"unprocessed": str(n)})


# ── Reliable webhook-independent sync ──────────────────────────────────────
# The events.watch → webhook → notification → drain path has proven unreliable
# in production: channels renew daily, but no notification has ever been
# processed (calendar_sync_job: 0 runs), so calendar data froze at its setup
# snapshot. Poll events.list?syncToken on a fixed cadence instead — the sensor
# above stays as a low-latency bonus path if/when the webhook is fixed.
# events_list() handles an expired (410) syncToken by falling back to a full pull.
calendar_polling_job = define_asset_job(
    "calendar_polling_job",
    selection=AssetSelection.assets(calendar_polling_fallback),
)


calendar_polling_schedule = ScheduleDefinition(
    job=calendar_polling_job,
    cron_schedule="*/15 * * * *",
    name="calendar_polling_schedule",
    description="Every 15m — poll events.list?syncToken per calendar (webhook-independent calendar sync).",
    default_status=DefaultScheduleStatus.RUNNING,
)
