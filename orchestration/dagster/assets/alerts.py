"""Run-failure alerting — auth.alerts row + email via Alertmanager.

A code-location-wide run_failure_sensor: whenever any run ends in FAILURE —
including runs that run_monitoring force-fails (stuck in STARTING past
start_timeout, or hung past max_runtime) — write one auth.alerts row (the
dashboard's /api/system/health surfaces those) AND post a DagsterRunFailure
alert to Alertmanager, which emails it through the alert-mailer Worker
(infrastructure/alert-mailer/). Each leg is independent: a failure of one
never blocks the other, and neither ever fails the sensor tick.

Gated to the VM: definitions.py only registers schedules/sensors when
DAGSTER_SCHEDULES_ENABLED=1, so this never fires on the dev laptop.
"""

from __future__ import annotations

import os

from dagster import (
    DefaultSensorStatus,
    RunFailureSensorContext,
    run_failure_sensor,
)


@run_failure_sensor(
    name="run_failure_alert_sensor",
    description="auth.alerts row + Alertmanager email on any run failure (incl. run_monitoring reaps).",
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

    am_url = os.environ.get("ALERTMANAGER_URL", "").rstrip("/")
    if not am_url:
        return
    try:
        import requests

        resp = requests.post(
            f"{am_url}/api/v2/alerts",
            json=[
                {
                    "labels": {
                        "alertname": "DagsterRunFailure",
                        "severity": "critical",
                        "dagster_job": run.job_name,
                    },
                    "annotations": {
                        "summary": f"Dagster job '{run.job_name}' failed",
                        "description": message,
                    },
                }
            ],
            timeout=10,
        )
        resp.raise_for_status()
        context.log.info("Posted DagsterRunFailure alert to Alertmanager")
    except Exception as exc:  # same rule: alerting must never fail the tick
        context.log.error("Failed to post alert to Alertmanager: %s", exc)
