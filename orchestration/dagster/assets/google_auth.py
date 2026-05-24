"""Google OAuth health monitoring.

If your GCP app is in **Production** publishing status, refresh tokens are
long-lived (revoked only on password change, 6 months of inactivity, or
manual revoke from myaccount.google.com). The weekly re-auth dance from
the original plan is no longer necessary in that mode — this asset
becomes an inactivity/rotation reminder instead of an expiry alarm.

Threshold is read from `GOOGLE_TOKEN_AGE_ALERT_DAYS` (default 90). If you
ever drop back to Testing-mode publishing, set it to 6 to get the weekly
behaviour back.

Re-auth still happens via the Pages Function flow (kept around as a
break-glass path):
  dashboard/functions/api/_internal/google-auth-{redirect,callback}.ts
"""

from __future__ import annotations

import os

from dagster import (
    AssetSelection,
    ScheduleDefinition,
    asset,
    define_asset_job,
)


def _alert_threshold_days() -> int:
    return int(os.environ.get("GOOGLE_TOKEN_AGE_ALERT_DAYS", "90"))


@asset(group_name="google", description="Inactivity reminder for Google tokens (default: > 90 days old).")
def google_token_health(context) -> dict:
    """Inspect auth.google_tokens.issued_at; alert when older than the threshold.

    In Production-mode GCP apps the refresh token doesn't expire on a fixed
    schedule, but stale tokens (6+ months of inactivity, password rotation,
    or a manual revoke) silently break ingest. This check exists so the
    dashboard can surface "consider rotating" before bronze actually goes
    stale.
    """
    from ingestion._shared.clickhouse import get_client, insert_rows

    threshold = _alert_threshold_days()

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
        return {"checked": 0, "alerts_raised": 0, "threshold_days": threshold}

    alerts = 0
    for email, issued_at, age_days in rows:
        context.log.info("Token age for %s: %d days (issued %s)", email, age_days, issued_at)
        if age_days >= threshold:
            insert_rows(
                "alerts",
                [
                    {
                        "kind": "token_stale",
                        "account_email": email,
                        "message": (
                            f"Google refresh token for {email} is {age_days} day(s) old "
                            f"(threshold {threshold}). Consider rotating via the Pages re-auth link."
                        ),
                    }
                ],
                database="auth",
                column_names=["kind", "account_email", "message"],
            )
            alerts += 1
    context.log.info("Checked %d tokens, raised %d alerts (threshold=%dd)", len(rows), alerts, threshold)
    return {"checked": len(rows), "alerts_raised": alerts, "threshold_days": threshold}


google_token_health_job = define_asset_job(
    "google_token_health_job",
    selection=AssetSelection.assets(google_token_health),
)


# Monthly is plenty for an inactivity check on a long-lived token.
google_token_health_schedule = ScheduleDefinition(
    job=google_token_health_job,
    cron_schedule="0 9 1 * *",  # 1st of the month, 09:00
    name="google_token_health_schedule",
    description="Monthly Google token inactivity check.",
)
