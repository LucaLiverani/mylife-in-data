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
        end_time_dt = pendulum.now('UTC')
        start_time_dt = end_time_dt.subtract(days=3)

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

        # Store job metadata
        job_metadata = {
            'job_id': job_id,
            'resource': resource,
            'initiated_at': pendulum.now('UTC').isoformat(),
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
        'resources': ['myactivity.maps'],  # Only Maps for this run
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

    # Initiate exports (dynamic based on params)
    # For now, hardcoded for YouTube and Maps
    # initiate_youtube_task = PythonOperator(
    #     task_id='initiate_myactivity_youtube_export',
    #     python_callable=initiate_export,
    #     op_kwargs={'resource': 'myactivity.youtube'},
    # )

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
    auth_task >> reset_task >> initiate_maps_task >> save_metadata_task
