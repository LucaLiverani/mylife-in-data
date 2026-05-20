# dags/google_export_initiator_dag.py
"""
Google Data Portability Export Initiator DAG

Initiates export jobs for Google services (YouTube, Maps).
Jobs are long-running (hours to days), so this DAG just starts them
and stores job metadata for the monitor DAG to process.

Run: Daily at midnight UTC (incremental exports of last 3 days)
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Dict, List

import pendulum
from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowException

from google_data_portability.data_portability_api import DataPortabilityClient

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Resources to export (can be configured per run)
DEFAULT_RESOURCES = ['myactivity.youtube', 'myactivity.maps']

# Use absolute paths relative to this DAG file
import os
DAG_DIR = os.path.dirname(__file__)
CLIENT_SECRETS_PATH = os.path.join(DAG_DIR, 'client_secrets.json')
TOKEN_CACHE_PATH = os.path.join(DAG_DIR, 'tokens', '.google_portability_token.pickle')

default_args = {
    'owner': 'data-engineering',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=15),
}

# ============================================================================
# Task 1: Authenticate (or verify existing token)
# ============================================================================

def authenticate_google(**context):
    """
    Authenticate with Google Data Portability API.
    Verifies token is valid and refreshes if needed.
    """
    log.info("Authenticating with Google Data Portability API...")

    try:
        # Initialize client (will auto-refresh token if needed)
        client = DataPortabilityClient(
            scopes=['youtube_activity', 'maps_activity'],
            client_secrets_file=CLIENT_SECRETS_PATH,
            token_cache_path=TOKEN_CACHE_PATH,
            port=8888
        )

        log.info("✓ Authentication successful")

        return {
            'status': 'authenticated',
            'timestamp': pendulum.now('UTC').isoformat(),
        }

    except Exception as e:
        log.error(f"Authentication failed: {e}")
        raise AirflowException(f"Failed to authenticate: {e}")

# ============================================================================
# Task 2: Reset Authorization (if needed)
# ============================================================================

def reset_authorization_if_needed(**context):
    """
    Reset authorization to clear any conflicting jobs.
    Only runs if manually triggered via Airflow Variable.

    Note: This cancels in-progress exports. Use only when needed.
    Set Variable 'google_portability_needs_reset' to 'true' to trigger.
    """
    ti = context['task_instance']

    # Check if we need to reset (can be set via Variable or previous run)
    should_reset = Variable.get('google_portability_needs_reset', default_var='false')

    if should_reset.lower() == 'true':
        log.info("Resetting authorization to clear conflicts...")

        try:
            client = DataPortabilityClient(
                scopes=['youtube_activity', 'maps_activity'],
                client_secrets_file=CLIENT_SECRETS_PATH,
                token_cache_path=TOKEN_CACHE_PATH,
                port=8888
            )

            client.reset_authorization()

            log.info("✓ Authorization reset successful")

            # Clear the flag
            Variable.set('google_portability_needs_reset', 'false')

            return {'status': 'reset', 'reason': 'conflict_detected'}

        except Exception as e:
            log.error(f"Reset failed: {e}")
            raise AirflowException(f"Failed to reset authorization: {e}")
    else:
        log.info("Authorization reset not needed")
        return {'status': 'skipped', 'reason': 'not_needed'}

# ============================================================================
# Task 3: Initiate Exports
# ============================================================================

def initiate_export(resource: str, **context):
    """
    Initiate a Google Data Portability export for a specific resource.

    Args:
        resource: Resource to export (e.g., 'myactivity.youtube')
    """
    ti = context['task_instance']
    logical_date = context.get('logical_date') or pendulum.now('UTC')

    log.info(f"Initiating export for resource: {resource}")

    # Check if we've exported this resource within the last 24 hours
    # Google API allows only 1 export per resource per 24 hours
    last_export_var_key = f'google_portability_last_export_{resource.replace(".", "_")}'

    try:
        last_export_time_str = Variable.get(last_export_var_key, default_var=None)
        if last_export_time_str:
            last_export_time = pendulum.parse(last_export_time_str)
            hours_since_last_export = (pendulum.now('UTC') - last_export_time).total_hours()

            if hours_since_last_export < 24:
                next_export_time = last_export_time.add(hours=24)
                log.warning(f"Export requested too soon for {resource}")
                log.info(f"Last export: {last_export_time.to_iso8601_string()}")
                log.info(f"Hours since last export: {hours_since_last_export:.1f}")
                log.info(f"Next export available at: {next_export_time.to_iso8601_string()}")
                log.info("Skipping export to comply with Google's 24-hour rate limit")

                return {
                    'job_id': None,
                    'resource': resource,
                    'status': 'SKIPPED_TOO_SOON',
                    'reason': 'less_than_24_hours_since_last_export',
                    'last_export': last_export_time.to_iso8601_string(),
                    'next_available': next_export_time.to_iso8601_string(),
                    'timestamp': pendulum.now('UTC').isoformat(),
                }
            else:
                log.info(f"Last export was {hours_since_last_export:.1f} hours ago - OK to proceed")
    except Exception as e:
        log.warning(f"Could not check last export time: {e} - proceeding with export")

    try:
        # Get appropriate scopes for resource
        if 'youtube' in resource:
            scopes = ['youtube_activity']
        elif 'maps' in resource:
            scopes = ['maps_activity']
        else:
            scopes = ['youtube_activity', 'maps_activity']

        client = DataPortabilityClient(
            scopes=scopes,
            client_secrets_file=CLIENT_SECRETS_PATH,
            token_cache_path=TOKEN_CACHE_PATH,
            port=8888
        )

        # Calculate time range for incremental export (last 3 days)
        # Use yesterday as end date to avoid "future time" errors
        end_time_dt = pendulum.now('UTC').subtract(days=1)
        start_time_dt = end_time_dt.subtract(days=30)  # 3 days total (including end day)

        start_time = start_time_dt.format('YYYY-MM-DD') + 'T00:00:00Z'
        end_time = end_time_dt.format('YYYY-MM-DD') + 'T23:59:59Z'

        log.info(f"Export time range: {start_time} to {end_time}")

        # Initiate export with time filters
        response = client.initiate_archive(
            resources=[resource],
            start_time=start_time,
            end_time=end_time
        )

        job_id = response.get('archiveJobId')

        log.info(f"✓ Export initiated successfully!")
        log.info(f"  Resource: {resource}")
        log.info(f"  Job ID: {job_id}")

        # Save the export timestamp to prevent duplicate exports within 24 hours
        export_time = pendulum.now('UTC')
        last_export_var_key = f'google_portability_last_export_{resource.replace(".", "_")}'
        Variable.set(last_export_var_key, export_time.to_iso8601_string())
        log.info(f"Saved last export time: {export_time.to_iso8601_string()}")

        # Store job metadata
        job_metadata = {
            'job_id': job_id,
            'resource': resource,
            'initiated_at': export_time.isoformat(),
            'initiated_by_dag': context['dag'].dag_id,
            'initiated_by_run_id': context['run_id'],
            'status': 'INITIATED',
            'last_checked': None,
            'logical_date': logical_date.isoformat(),
        }

        # Push to XCom
        ti.xcom_push(key=f'job_metadata_{resource}', value=job_metadata)

        return job_metadata

    except Exception as e:
        error_msg = str(e)

        # Check for 409 Conflict
        if '409' in error_msg and 'Conflict' in error_msg:
            log.warning(f"Conflict detected for {resource} - job already running")
            log.info("Skipping this run. The monitor DAG will handle the existing export.")
            log.info("Next daily run will start a new export once the current one completes.")

            # Return a placeholder to indicate we skipped
            return {
                'job_id': None,
                'resource': resource,
                'status': 'SKIPPED_CONFLICT',
                'reason': 'export_already_in_progress',
                'timestamp': pendulum.now('UTC').isoformat(),
            }

        # Check for 429 Rate Limit (Google allows export once per 24 hours)
        elif '429' in error_msg and ('RESOURCE_EXHAUSTED' in error_msg or 'Too Many Requests' in error_msg):
            log.warning(f"Rate limit reached for {resource} - already exported within 24 hours")
            log.info("Google Data Portability API limits: 1 export per resource per 24 hours")

            # Extract next available time from error message
            import re
            next_export_match = re.search(r'after (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)', error_msg)
            next_export_time_str = next_export_match.group(1) if next_export_match else None

            if next_export_time_str:
                next_export_time = pendulum.parse(next_export_time_str)
                log.info(f"Next export available at: {next_export_time.to_iso8601_string()}")

                # Update the last export variable to prevent retries before this time
                last_export_var_key = f'google_portability_last_export_{resource.replace(".", "_")}'
                # Calculate when the last export happened (24 hours before next available time)
                last_export_time = next_export_time.subtract(hours=24)
                Variable.set(last_export_var_key, last_export_time.to_iso8601_string())
                log.info(f"Updated last export time to: {last_export_time.to_iso8601_string()}")
            else:
                log.warning("Could not extract next export time from error message")
                next_export_time_str = 'unknown'

            # Return a placeholder to indicate we skipped due to rate limit
            return {
                'job_id': None,
                'resource': resource,
                'status': 'SKIPPED_RATE_LIMIT',
                'reason': 'already_exported_within_24_hours',
                'next_available': next_export_time_str,
                'timestamp': pendulum.now('UTC').isoformat(),
            }

        else:
            log.error(f"Failed to initiate export: {e}")
            raise AirflowException(f"Failed to initiate export for {resource}: {e}")

# ============================================================================
# Task 4: Save Job Metadata
# ============================================================================

def save_job_metadata(**context):
    """
    Save job metadata to Airflow Variables for the monitor DAG to process.
    """
    ti = context['task_instance']

    # Collect all job metadata from previous tasks
    resources = context['params'].get('resources', DEFAULT_RESOURCES)

    pending_jobs = []

    for resource in resources:
        job_metadata = ti.xcom_pull(
            task_ids=f'initiate_{resource.replace(".", "_")}_export',
            key=f'job_metadata_{resource}'
        )

        if job_metadata:
            # Skip jobs that had conflicts (no job_id means skipped)
            if job_metadata.get('job_id') is not None:
                pending_jobs.append(job_metadata)
                log.info(f"Collected job metadata for {resource}: {job_metadata['job_id']}")
            else:
                log.info(f"Skipped {resource} - export already in progress")

    if not pending_jobs:
        log.warning("No jobs were initiated successfully")
        return {'status': 'no_jobs', 'count': 0}

    # Get existing pending jobs
    try:
        existing_jobs_json = Variable.get('google_portability_pending_jobs', default_var='[]')
        existing_jobs = json.loads(existing_jobs_json)
    except:
        existing_jobs = []

    # Add new jobs
    existing_jobs.extend(pending_jobs)

    # Save back to Variable
    Variable.set('google_portability_pending_jobs', json.dumps(existing_jobs))

    log.info(f"✓ Saved {len(pending_jobs)} pending job(s)")
    log.info(f"Total pending jobs: {len(existing_jobs)}")

    return {
        'status': 'saved',
        'new_jobs': len(pending_jobs),
        'total_pending': len(existing_jobs),
        'job_ids': [j['job_id'] for j in pending_jobs],
    }

# ============================================================================
# Define DAG
# ============================================================================

with DAG(
    dag_id="google_export_initiator",
    default_args=default_args,
    description="Initiate Google Data Portability exports (YouTube, Maps) - Last 3 days",
    schedule="0 0 * * *",  # Daily at midnight UTC
    start_date=pendulum.datetime(2025, 12, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["google", "data-portability", "export", "initiator", "incremental"],
    params={
        'resources': ['myactivity.youtube', 'myactivity.maps'],  # YouTube and Maps
    },
) as dag:

    # Authenticate
    auth_task = PythonOperator(
        task_id='authenticate',
        python_callable=authenticate_google,
    )

    # Reset authorization if needed
    reset_task = PythonOperator(
        task_id='reset_authorization_if_needed',
        python_callable=reset_authorization_if_needed,
    )

    # Initiate exports for YouTube and Maps
    initiate_youtube_task = PythonOperator(
        task_id='initiate_myactivity_youtube_export',
        python_callable=initiate_export,
        op_kwargs={'resource': 'myactivity.youtube'},
    )

    initiate_maps_task = PythonOperator(
        task_id='initiate_myactivity_maps_export',
        python_callable=initiate_export,
        op_kwargs={'resource': 'myactivity.maps'},
    )

    # Save job metadata
    save_metadata_task = PythonOperator(
        task_id='save_job_metadata',
        python_callable=save_job_metadata,
        trigger_rule='all_done',  # Run even if some exports fail
    )

    # Dependencies
    # Run YouTube and Maps exports in parallel after authentication
    auth_task >> reset_task >> [initiate_youtube_task, initiate_maps_task] >> save_metadata_task
