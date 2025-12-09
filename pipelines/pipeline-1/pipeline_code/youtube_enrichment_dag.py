# dags/youtube_enrichment.py
from __future__ import annotations

import sys
import os
import logging
from datetime import timedelta

import pendulum
from airflow.models.dag import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.exceptions import AirflowException

# Add pipeline_code directory to Python path for imports
pipeline_code_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, pipeline_code_dir)

from youtube_enrichment import config
from youtube_enrichment.youtube_api_client import create_client
from youtube_enrichment.utils import ClickHouseClient
from youtube_enrichment.storage import create_storage
from youtube_enrichment.enrich_youtube_videos import YouTubeEnricher

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Default number of videos to process per run (None = all available)
DEFAULT_VIDEO_LIMIT = 500  # Process 500 videos per run to stay within quota


def get_clickhouse_connection():
    """Get ClickHouse connection details from Airflow connection."""
    from airflow.hooks.base import BaseHook

    conn = BaseHook.get_connection('clickhouse_default')
    # clickhouse_connect uses HTTP interface (port 8123), not native protocol (9000)
    # If Airflow connection has port 9000, convert to 8123
    port = conn.port
    if port == 9000:
        port = 8123  # Use HTTP interface
    elif port is None:
        port = 8123  # Default to HTTP interface

    return {
        'host': conn.host,
        'port': port,
        'user': conn.login,
        'password': conn.password,
        'database': conn.extra_dejson.get('database', 'default')
    }


default_args = {
    'owner': 'data-engineering',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

# ============================================================================
# Task: Enrich YouTube Videos
# ============================================================================

def enrich_youtube_videos(**context):
    """
    Enrich YouTube watch history with video metadata from YouTube Data API v3.

    Fetches video metadata (channel info, duration, categories) and stores
    enriched data to MinIO in JSONL.gz format.

    Returns:
        dict: Summary of enrichment run
    """
    logical_date = context.get('logical_date')
    run_id = context['run_id']
    ti = context['task_instance']

    log.info("=" * 60)
    log.info("Starting YouTube Video Enrichment")
    log.info(f"Logical date: {logical_date}")
    log.info(f"Run ID: {run_id}")
    log.info("=" * 60)

    # Validate configuration
    if not config.validate_config():
        raise AirflowException("Configuration validation failed. Check YouTube API credentials and ClickHouse connection.")

    try:
        # Initialize clients
        log.info("Initializing clients...")

        # Get ClickHouse connection from Airflow
        ch_conn_params = get_clickhouse_connection()
        log.info(f"Connecting to ClickHouse at {ch_conn_params['host']}:{ch_conn_params['port']}")

        youtube_client = create_client()
        ch_client = ClickHouseClient(
            host=ch_conn_params['host'],
            port=ch_conn_params['port'],
            user=ch_conn_params['user'],
            password=ch_conn_params['password'],
            database=ch_conn_params['database']
        )
        storage_client = create_storage(use_local=False)  # Always use MinIO in production

        # Create enricher
        enricher = YouTubeEnricher(
            youtube_client=youtube_client,
            clickhouse_client=ch_client,
            storage_client=storage_client,
            dry_run=False,
        )

        # Run enrichment with limit to avoid quota exhaustion
        log.info(f"Running enrichment (limit: {DEFAULT_VIDEO_LIMIT} videos)...")
        summary = enricher.run(limit=DEFAULT_VIDEO_LIMIT)

        # Close connections
        ch_client.close()

        # Push summary to XCom
        ti.xcom_push(key='enrichment_summary', value=summary)

        # Log summary
        log.info("=" * 60)
        log.info("Enrichment Summary:")
        log.info(f"  Status: {summary['status']}")
        log.info(f"  Videos processed: {summary.get('processed', 0)}")
        log.info(f"  Successful: {summary.get('successful', 0)}")
        log.info(f"  Failed: {summary.get('failed', 0)}")
        log.info(f"  Elapsed: {summary.get('elapsed_seconds', 0):.1f}s")
        log.info(f"  Quota used: {summary.get('quota_used', 0)}")
        log.info(f"  Quota remaining: {summary.get('quota_remaining', 0)}")
        log.info("=" * 60)

        # Check for failures
        if summary['status'] == 'quota_exceeded':
            raise AirflowException("YouTube API quota exceeded. Try again after quota reset (midnight PST).")

        if summary['status'] == 'nothing_to_enrich':
            log.info("No videos need enrichment. All videos are already enriched.")
            return summary

        # Warn if too many failures
        if summary.get('failed', 0) > 0:
            failure_rate = summary['failed'] / summary['processed']
            if failure_rate > 0.1:  # More than 10% failure rate
                log.warning(f"High failure rate: {failure_rate:.1%} ({summary['failed']}/{summary['processed']})")

        return summary

    except Exception as e:
        log.error(f"Enrichment failed: {e}", exc_info=True)
        raise AirflowException(f"YouTube enrichment failed: {e}")

# ============================================================================
# Define DAG
# ============================================================================

with DAG(
    dag_id="youtube_enrichment",
    default_args=default_args,
    description="Enrich YouTube watch history with video metadata from YouTube Data API v3",
    schedule="0 2 * * *",  # Daily at 2 AM UTC
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,  # Only one enrichment run at a time
    tags=["youtube", "enrichment", "ingestion"],
) as dag:

    # Enrich videos
    enrich_task = PythonOperator(
        task_id='enrich_youtube_videos',
        python_callable=enrich_youtube_videos,
    )

    # Simple linear flow
    enrich_task
