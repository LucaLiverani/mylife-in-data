"""Google OAuth health monitoring.

Token expiry is the one inescapable manual step (see IMPLEMENTATION_PLAN.md §2):
external-user-type apps in Testing publishing mode get refresh tokens that
expire after 7 days. This module:

  - runs a weekly `@schedule` to check token age and raise alerts when a
    re-auth is due
  - exposes the alerts via auth.alerts for the dashboard/system-health page

The actual re-auth happens via the Pages Function flow
(dashboard/functions/api/_internal/google-auth-{redirect,callback}.ts).
"""

from __future__ import annotations

from dagster import (
    AssetSelection,
    ScheduleDefinition,
    asset,
    define_asset_job,
)


@asset(group_name="google", description="Check Google token age; alert when re-auth is due.")
def google_token_health(context) -> dict:
    """Inspect auth.google_tokens.issued_at; alert when > 6 days old."""
    from ingestion._shared.clickhouse import get_client, insert_rows

    client = get_client()
    rows = client.query(
        "SELECT account_email, issued_at, "
        "dateDiff('day', issued_at, now()) AS age_days "
        "FROM auth.google_tokens FINAL"
    ).result_rows

    if not rows:
        context.log.warning(
            "auth.google_tokens is empty — run scripts/bootstrap_google_auth.py "
            "on your laptop to seed the first token."
        )
        return {"checked": 0, "alerts_raised": 0}

    alerts = 0
    for email, issued_at, age_days in rows:
        context.log.info("Token age for %s: %d days (issued %s)", email, age_days, issued_at)
        if age_days >= 6:
            insert_rows(
                "alerts",
                [
                    {
                        "kind": "token_expiring",
                        "account_email": email,
                        "message": (
                            f"Google refresh token for {email} is {age_days} day(s) old. "
                            f"Click the re-auth link to renew."
                        ),
                    }
                ],
                database="auth",
                column_names=["kind", "account_email", "message"],
            )
            alerts += 1
    context.log.info("Checked %d tokens, raised %d alerts", len(rows), alerts)
    return {"checked": len(rows), "alerts_raised": alerts}


google_token_health_job = define_asset_job(
    "google_token_health_job",
    selection=AssetSelection.assets(google_token_health),
)


google_token_health_schedule = ScheduleDefinition(
    job=google_token_health_job,
    cron_schedule="0 9 * * 1",  # Monday 09:00
    name="google_token_health_schedule",
    description="Weekly Google token freshness check.",
)
