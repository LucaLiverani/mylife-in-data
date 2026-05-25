"""Cross-source freshness monitor — surfaces stale ingest as auth.alerts rows.

Runs daily. Per source, computes seconds since the latest bronze row; if it's
beyond the configured budget, INSERTs an alert. The dashboard's /api/system/health
handler reads these directly.
"""

from __future__ import annotations

from datetime import timedelta

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    ScheduleDefinition,
    asset,
    define_asset_job,
)


# Per-source freshness budgets in seconds. Tuned to the pipeline cadence:
# Spotify currently-playing should poll every 5s; daily DP-based sources have
# a 36h grace window to account for archive-job latency.
FRESHNESS_BUDGET_S: dict[str, int] = {
    "spotify_current": 300,         # 5 min
    "spotify_history": 86400,       # 24h
    "youtube":         86400 * 2,   # 48h (DP archive can lag)
    "maps":            86400 * 2,   # 48h
    "calendar":        86400 * 2,   # 48h (push channel + sync sensor)
}


_FRESHNESS_SQL = """
WITH sources AS (
    SELECT 'spotify_current' AS source, max(captured_at) AS latest FROM bronze.spotify_player_current
    UNION ALL
    SELECT 'spotify_history', max(played_at) FROM bronze.spotify_plays_raw
    UNION ALL
    SELECT 'youtube', max(watched_at) FROM bronze.youtube_watch_history
    UNION ALL
    SELECT 'maps', max(started_at) FROM bronze.maps_visits
    UNION ALL
    SELECT 'calendar', max(started_at) FROM bronze.calendar_events
)
SELECT
    source,
    latest,
    dateDiff('second', latest, now()) AS seconds_since
FROM sources
"""


@asset(group_name="observability", description="Per-source freshness check; raises alerts when stale.")
def freshness_monitor(context) -> dict:
    from ingestion._shared.clickhouse import get_client, insert_rows

    client = get_client()
    rows = client.query(_FRESHNESS_SQL).result_rows
    alerts = []
    summary = {}
    for source, latest, seconds_since in rows:
        budget = FRESHNESS_BUDGET_S.get(source, 86400)
        summary[source] = {"latest": str(latest), "seconds_since": int(seconds_since or 0)}
        # Tables with no rows yet have seconds_since = NULL or huge; only flag
        # when the table HAS rows but the latest one is stale.
        if latest is None:
            continue
        if (seconds_since or 0) > budget:
            alerts.append(
                {
                    "kind": "freshness_breach",
                    "account_email": "",
                    "message": (
                        f"{source} stale: latest row {seconds_since}s ago "
                        f"(budget {budget}s)"
                    ),
                }
            )

    if alerts:
        insert_rows(
            "alerts",
            alerts,
            database="auth",
            column_names=["kind", "account_email", "message"],
        )
    context.log.info("Freshness: %s — %d alert(s) raised", summary, len(alerts))
    return {"sources": summary, "alerts_raised": len(alerts)}


freshness_monitor_job = define_asset_job(
    "freshness_monitor_job",
    selection=AssetSelection.assets(freshness_monitor),
)


freshness_monitor_schedule = ScheduleDefinition(
    job=freshness_monitor_job,
    cron_schedule="0 8 * * *",
    name="freshness_monitor_schedule",
    description="Daily 08:00 cross-source freshness check.",
    default_status=DefaultScheduleStatus.RUNNING,
)
