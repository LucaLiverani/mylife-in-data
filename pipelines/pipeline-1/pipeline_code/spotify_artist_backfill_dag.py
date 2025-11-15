# dags/spotify_artist_backfill_dag.py
"""
One-time DAG to backfill artist details for all artists in the tracks table.

This DAG:
1. Queries ClickHouse for all unique artist IDs from tracks
2. Fetches artist details from Spotify API (batch of 50)
3. Saves to S3 and publishes to Kafka

Run this manually once to populate the artist dimension table.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import List

import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.exceptions import AirflowException
from kafka import KafkaProducer
from kafka.errors import KafkaError
from clickhouse_driver import Client as ClickHouseClient

from spotify.spotify_api import get_spotify_client, get_artists

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BUCKET_NAME = "inbound"
RAW_FILE_FOLDER = "raw/spotify/api/artists"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_ARTISTS_RAW_TOPIC = "spotify.artists.raw"
CLICKHOUSE_HOST = "clickhouse"
CLICKHOUSE_PORT = 9000
CLICKHOUSE_DATABASE = "bronze"
CLICKHOUSE_USER = "admin"
CLICKHOUSE_PASSWORD = "clickhouse08062013"
SPOTIFY_BATCH_SIZE = 50

default_args = {
    'owner': 'data-engineering',
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=60),
}

# ============================================================================
# Task 1: Extract Artist IDs from Tracks
# ============================================================================

def extract_artist_ids_from_tracks(**context):
    """
    Query ClickHouse for all unique artist IDs from tracks table.
    Returns list of artist IDs to fetch.
    """
    ti = context['task_instance']

    log.info("Connecting to ClickHouse to extract artist IDs...")

    client = ClickHouseClient(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE
    )

    # Query for all unique artist IDs from tracks
    # Also gets from the artists array for multi-artist tracks
    query = """
    SELECT DISTINCT artist_id
    FROM (
        SELECT artist_id FROM bronze.raw_spotify_tracks WHERE artist_id != ''
        UNION ALL
        SELECT arrayJoin(artists_ids) AS artist_id FROM bronze.raw_spotify_tracks
    )
    WHERE artist_id != ''
    """

    try:
        result = client.execute(query)
        artist_ids = [row[0] for row in result]

        log.info(f"Found {len(artist_ids)} unique artist IDs from tracks table")

        # Push to XCom
        ti.xcom_push(key='artist_ids', value=artist_ids)
        ti.xcom_push(key='artist_count', value=len(artist_ids))

        return len(artist_ids)

    except Exception as e:
        log.error(f"Failed to extract artist IDs: {e}")
        raise AirflowException(f"ClickHouse query failed: {e}")
    finally:
        client.disconnect()

# ============================================================================
# Task 2: Fetch Artist Details from Spotify
# ============================================================================

def fetch_all_artist_details(**context):
    """
    Fetch artist details from Spotify API in batches of 50.
    """
    ti = context['task_instance']
    execution_date = context['execution_date']
    run_id = context['run_id']

    artist_ids = ti.xcom_pull(task_ids='extract_artist_ids', key='artist_ids')

    if not artist_ids:
        log.info("No artist IDs to fetch")
        ti.xcom_push(key='artist_details', value=[])
        return []

    sp = get_spotify_client()

    log.info(f"Fetching details for {len(artist_ids)} artists in batches of {SPOTIFY_BATCH_SIZE}...")

    all_artist_details = []
    success_count = 0
    error_count = 0

    # Process in batches
    for i in range(0, len(artist_ids), SPOTIFY_BATCH_SIZE):
        batch = artist_ids[i:i + SPOTIFY_BATCH_SIZE]
        batch_num = (i // SPOTIFY_BATCH_SIZE) + 1
        total_batches = (len(artist_ids) + SPOTIFY_BATCH_SIZE - 1) // SPOTIFY_BATCH_SIZE

        log.info(f"Fetching batch {batch_num}/{total_batches} ({len(batch)} artists)")

        try:
            # Fetch batch from Spotify
            response = get_artists(sp, batch)

            if not response or 'artists' not in response:
                log.error(f"Invalid response for batch {batch_num}")
                error_count += len(batch)
                continue

            # Add ingestion metadata to each artist
            for artist in response['artists']:
                if artist is None:
                    error_count += 1
                    continue

                artist_with_metadata = {
                    'raw_artist': artist,
                    '_ingestion_metadata': {
                        'ingested_at': pendulum.now('UTC').isoformat(),
                        'execution_date': execution_date.isoformat(),
                        'dag_id': context['dag'].dag_id,
                        'run_id': run_id,
                        'source': 'spotify_api_backfill',
                        'batch_number': batch_num,
                    }
                }

                all_artist_details.append(artist_with_metadata)
                success_count += 1

        except Exception as e:
            log.error(f"Failed to fetch batch {batch_num}: {e}")
            error_count += len(batch)
            continue

    log.info(f"Fetched {success_count} artists successfully, {error_count} failed")

    # Push to XCom
    ti.xcom_push(key='artist_details', value=all_artist_details)
    ti.xcom_push(key='artist_details_count', value=len(all_artist_details))

    if error_count > len(artist_ids) * 0.5:
        raise AirflowException(f"Too many failures: {error_count}/{len(artist_ids)}")

    return all_artist_details

# ============================================================================
# Task 3: Publish to Kafka
# ============================================================================

def publish_artists_to_kafka(**context):
    """Publish artist details to Kafka"""
    ti = context['task_instance']

    artist_details = ti.xcom_pull(task_ids='fetch_artist_details', key='artist_details')

    if not artist_details:
        log.info("No artist details to publish")
        return {'status': 'skipped', 'published': 0}

    log.info(f"Publishing {len(artist_details)} artists to Kafka...")

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
        compression_type='snappy',
        linger_ms=100,
    )

    success_count = 0
    error_count = 0

    try:
        for artist in artist_details:
            try:
                artist_id = artist['raw_artist'].get('id', f"unknown_{success_count}")

                producer.send(
                    topic=KAFKA_ARTISTS_RAW_TOPIC,
                    value=artist,
                    key=artist_id,
                )

                success_count += 1

            except KafkaError as e:
                error_count += 1
                log.error(f"Failed to publish artist: {e}")
                continue

        producer.flush(timeout=30)

        result = {
            'status': 'success' if error_count == 0 else 'partial_success',
            'topic': KAFKA_ARTISTS_RAW_TOPIC,
            'published': success_count,
            'failed': error_count,
            'total': len(artist_details),
        }

        ti.xcom_push(key='kafka_result', value=result)
        log.info(f"Published {success_count}/{len(artist_details)} artists to Kafka")

        return result

    finally:
        producer.close()

# ============================================================================
# Task 4: Save to S3
# ============================================================================

def save_artists_to_s3(**context):
    """Save artist details to S3 as JSONL file"""
    ti = context['task_instance']
    execution_date = context['execution_date']
    s3_hook = S3Hook(aws_conn_id="minio_s3")

    artist_details = ti.xcom_pull(task_ids='fetch_artist_details', key='artist_details')

    if not artist_details:
        log.info("No artist details to save")
        return {'status': 'skipped'}

    # S3 key for backfill file
    date_str = execution_date.format('YYYY-MM-DD')
    key = f"{RAW_FILE_FOLDER}/backfill_{date_str}.jsonl"

    log.info(f"Saving {len(artist_details)} artists to s3://{BUCKET_NAME}/{key}")

    try:
        # Write to JSONL format
        jsonl_lines = [json.dumps(artist, default=str) for artist in artist_details]
        content = '\n'.join(jsonl_lines)

        # Upload to S3
        s3_hook.load_string(
            content,
            key=key,
            bucket_name=BUCKET_NAME,
            replace=True
        )

        result = {
            'status': 'success',
            's3_path': f"s3://{BUCKET_NAME}/{key}",
            'artists_saved': len(artist_details),
        }

        ti.xcom_push(key='s3_result', value=result)
        log.info(f"Saved {len(artist_details)} artists to S3")

        return result

    except Exception as e:
        log.error(f"Failed to save to S3: {e}", exc_info=True)
        raise AirflowException(f"S3 save failed: {e}")

# ============================================================================
# Task 5: Summary
# ============================================================================

def log_backfill_summary(**context):
    """Log summary of backfill operation"""
    ti = context['task_instance']

    artist_count = ti.xcom_pull(task_ids='extract_artist_ids', key='artist_count')
    fetched_count = ti.xcom_pull(task_ids='fetch_artist_details', key='artist_details_count')
    kafka_result = ti.xcom_pull(task_ids='publish_to_kafka', key='kafka_result')
    s3_result = ti.xcom_pull(task_ids='save_to_s3', key='s3_result')

    log.info("=" * 60)
    log.info("ARTIST BACKFILL SUMMARY")
    log.info("=" * 60)
    log.info(f"Unique artists in tracks table: {artist_count}")
    log.info(f"Artists fetched from Spotify: {fetched_count}")
    log.info(f"Artists published to Kafka: {kafka_result.get('published', 0) if kafka_result else 0}")
    log.info(f"Artists saved to S3: {s3_result.get('artists_saved', 0) if s3_result else 0}")
    log.info("=" * 60)
    log.info("Backfill complete! Artist details will be auto-ingested by S3Queue.")
    log.info("=" * 60)

# ============================================================================
# Define DAG
# ============================================================================

with DAG(
    dag_id="spotify_artist_backfill",
    default_args=default_args,
    description="One-time backfill: Fetch artist details for all artists in tracks table",
    schedule_interval=None,  # Manual trigger only
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["spotify", "artists", "backfill", "one-time"],
) as dag:

    # Extract artist IDs
    extract_task = PythonOperator(
        task_id='extract_artist_ids',
        python_callable=extract_artist_ids_from_tracks,
    )

    # Fetch artist details
    fetch_task = PythonOperator(
        task_id='fetch_artist_details',
        python_callable=fetch_all_artist_details,
    )

    # Publish to Kafka
    kafka_task = PythonOperator(
        task_id='publish_to_kafka',
        python_callable=publish_artists_to_kafka,
    )

    # Save to S3
    s3_task = PythonOperator(
        task_id='save_to_s3',
        python_callable=save_artists_to_s3,
    )

    # Summary
    summary_task = PythonOperator(
        task_id='log_summary',
        python_callable=log_backfill_summary,
    )

    # Dependencies
    extract_task >> fetch_task >> [kafka_task, s3_task] >> summary_task
