"""Run-failure alerting — writes to the existing auth.alerts table (no email).

A code-location-wide run_failure_sensor: whenever any run ends in FAILURE —
including runs that run_monitoring force-fails (stuck in STARTING past
start_timeout, or hung past max_runtime) — write one auth.alerts row. The
dashboard's /api/system/health already surfaces auth.alerts (freshness +
token-age), so failed jobs appear where the other operator alerts live, with no
email channel to maintain.

To add email later, send from inside the sensor body (e.g. POST to a provider)
alongside the auth.alerts insert.

Gated to the VM: definitions.py only registers schedules/sensors when
DAGSTER_SCHEDULES_ENABLED=1, so this never fires on the dev laptop.
"""

from __future__ import annotations

from dagster import (
    DefaultSensorStatus,
    RunFailureSensorContext,
    run_failure_sensor,
)


@run_failure_sensor(
    name="run_failure_alert_sensor",
    description="Write an auth.alerts row on any run failure (incl. run_monitoring reaps).",
    default_status=DefaultSensorStatus.RUNNING,
)
def run_failure_alert_sensor(context: RunFailureSensorContext) -> None:
    from ingestion._shared.clickhouse import insert_rows

    run = context.dagster_run
    reason = (context.failure_event.message or "unknown error").strip()
    message = f"Job '{run.job_name}' run {run.run_id[:8]} failed: {reason}"[:2000]
    try:
        insert_rows(
            "alerts",
            [{"kind": "run_failure", "account_email": "", "message": message}],
            database="auth",
            column_names=["kind", "account_email", "message"],
        )
        context.log.info("Recorded run_failure alert: %s", message)
    except Exception as exc:  # never let an alert-write failure fail the sensor tick
        context.log.error("Failed to write run_failure alert: %s", exc)
