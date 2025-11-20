# dags/spotify_artist_ingestion_dag.py
from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Dict, List, Set

import pendulum
from airflow.models.dag import DAG
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.exceptions import AirflowException
from kafka import KafkaProducer, KafkaConsumer
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
KAFKA_ARTIST_IDS_TOPIC = "spotify.artist_ids"
KAFKA_ARTISTS_RAW_TOPIC = "spotify.artists.raw"
ARTIST_REFRESH_DAYS = 7  # Re-fetch artists older than this

SPOTIFY_BATCH_SIZE = 50  # Spotify API allows 50 artists per request


def get_clickhouse_connection():
    """Get ClickHouse connection details from Airflow connection."""
    from airflow.hooks.base import BaseHook

    conn = BaseHook.get_connection('clickhouse_default')
    return {
        'host': conn.host,
        'port': conn.port or 9000,
        'user': conn.login,
        'password': conn.password,
        'database': conn.extra_dejson.get('database', 'bronze')
    }

default_args = {
    'owner': 'data-engineering',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=15),
}

# ============================================================================ 
# Task 1: Collect Artist IDs to Fetch
# ============================================================================ 

def collect_artist_ids_to_fetch(**context):
    """
    Collect artist IDs from:
    1. Kafka topic (newly discovered artists)
    2. ClickHouse (artists needing refresh)

    Returns unique list of artist IDs that need fetching.
    """
    ti = context['task_instance']
    logical_date = context['logical_date']

    artist_ids_to_fetch = set()

    # 1. Consume from Kafka (newly discovered artist IDs)
    log.info("Consuming artist IDs from Kafka...")
    try:
        consumer = KafkaConsumer(
            KAFKA_ARTIST_IDS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id=f'artist_ingestion_{logical_date.format("YYYY-MM-DD")}',
            consumer_timeout_ms=10000,  # Stop after 10s of no messages
        )

        kafka_count = 0
        for message in consumer:
            artist_id = message.value.get('artist_id')
            if artist_id:
                artist_ids_to_fetch.add(artist_id)
                kafka_count += 1

        consumer.close()
        log.info(f"Found {kafka_count} artist IDs from Kafka")

    except Exception as e:
        log.warning(f"Failed to consume from Kafka: {e}")

    # 2. Query ClickHouse for artists needing refresh
    log.info("Querying ClickHouse for stale artists...")
    try:
        # Get connection details from Airflow connection
        conn_params = get_clickhouse_connection()
        client = ClickHouseClient(**conn_params)

        # Find artists older than refresh period
        refresh_threshold = pendulum.now('UTC').subtract(days=ARTIST_REFRESH_DAYS)

        query = """
        SELECT DISTINCT artist_id
        FROM spotify_artists
        WHERE last_updated < %(threshold)s
        LIMIT 1000
        """

        result = client.execute(
            query,
            {'threshold': refresh_threshold.to_datetime_string()}
        )

        stale_count = 0
        for row in result:
            artist_ids_to_fetch.add(row[0])
            stale_count += 1

        log.info(f"Found {stale_count} stale artists from ClickHouse")

        client.disconnect()

    except Exception as e:
        log.warning(f"Failed to query ClickHouse: {e}")

    # Convert to list for XCom
    artist_ids_list = list(artist_ids_to_fetch)

    log.info(f"Total unique artist IDs to fetch: {len(artist_ids_list)}")

    ti.xcom_push(key='artist_ids_to_fetch', value=artist_ids_list)
    ti.xcom_push(key='artist_count', value=len(artist_ids_list))

    return len(artist_ids_list)

# ============================================================================ 
# Task 2: Branch - Skip if No Artists
# ============================================================================ 

def check_for_artists(**context):
    """Branch: Skip if no artists to fetch"""
    ti = context['task_instance']
    artist_count = ti.xcom_pull(task_ids='collect_artist_ids', key='artist_count')

    if artist_count == 0:
        log.info("No artists to fetch, skipping")
        return 'skip_processing'
    else:
        log.info(f"Found {artist_count} artists to fetch, proceeding")
        return 'fetch_artist_details'

# ============================================================================ 
# Task 3: Fetch Artist Details from Spotify API
# ============================================================================ 

def fetch_artist_details(**context):
    """
    Fetch artist details from Spotify API in batches of 50.
    Returns raw artist data with ingestion metadata.
    """
    ti = context['task_instance']
    logical_date = context['logical_date']
    run_id = context['run_id']

    artist_ids = ti.xcom_pull(task_ids='collect_artist_ids', key='artist_ids_to_fetch')

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
                    'raw_artist': artist,  # Untouched API response
                    '_ingestion_metadata': {
                        'ingested_at': pendulum.now('UTC').isoformat(),
                        'logical_date': logical_date.isoformat(),
                        'dag_id': context['dag'].dag_id,
                        'run_id': run_id,
                        'source': 'spotify_api',
                        'batch_number': batch_num,
                    }
                }

                all_artist_details.append(artist_with_metadata)
                success_count += 1

        except Exception as e:
            log.error(f"Failed to fetch batch {batch_num}: {e}")
            error_count += len(batch)
            continue

    log.info(
        f"Fetched {success_count} artists successfully, "
        f"{error_count} failed"
    )

    # Push to XCom
    ti.xcom_push(key='artist_details', value=all_artist_details)
    ti.xcom_push(key='artist_details_count', value=len(all_artist_details))

    if error_count > len(artist_ids) * 0.5:
        raise AirflowException(f"Too many failures: {error_count}/{len(artist_ids)}")

    return all_artist_details

# ============================================================================ 
# Task 4: Publish to Kafka
# ============================================================================ 

def publish_artists_to_kafka(**context):
    """
    Publish artist details to Kafka.
    """
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
                # Key = artist_id
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

        if error_count > len(artist_details) * 0.1:
            raise AirflowException(f"Too many Kafka failures: {error_count}/{len(artist_details)}")

        return result

    finally:
        producer.close()

# ============================================================================ 
# Task 5: Save to S3
# ============================================================================ 

def save_artists_to_s3(**context):
    """
    Save artist details to S3 as daily JSONL file.
    Appends to existing file if present.
    """
    ti = context['task_instance']
    logical_date = context['logical_date']
    s3_hook = S3Hook(aws_conn_id="minio_s3")

    artist_details = ti.xcom_pull(task_ids='fetch_artist_details', key='artist_details')

    if not artist_details:
        log.info("No artist details to save")
        return {'status': 'skipped'}

    # S3 key for today's file
    date_str = logical_date.format('YYYY-MM-DD')
    key = f"{RAW_FILE_FOLDER}/{date_str}.jsonl"

    log.info(f"Saving {len(artist_details)} artists to s3://{BUCKET_NAME}/{key}")

    try:
        existing_lines = []

        # Check if file exists
        if s3_hook.check_for_key(key, BUCKET_NAME):
            log.info("Existing file found, appending...")
            s3_obj = s3_hook.get_key(key, BUCKET_NAME)
            existing_content = s3_obj.get()["Body"].read().decode('utf-8')
            existing_lines = existing_content.strip().split('\n')
            log.info(f"Loaded {len(existing_lines)} existing entries")

        # Append new artist details
        new_lines = [json.dumps(artist, default=str) for artist in artist_details]
        all_lines = existing_lines + new_lines

        # Write back to S3
        content = '\n'.join(all_lines)
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
            'total_artists': len(all_lines),
        }

        ti.xcom_push(key='s3_result', value=result)

        log.info(
            f"Saved {len(artist_details)} new artists to S3 "
            f"(total in file: {len(all_lines)})"
        )

        return result

    except Exception as e:
        log.error(f"Failed to save to S3: {e}", exc_info=True)
        raise AirflowException(f"S3 save failed: {e}")

# ============================================================================ 
# Task 6: Validate
# ============================================================================ 

def validate_outputs(**context):
    """Validate artist ingestion"""
    ti = context['task_instance']

    # Check if processing was skipped
    artist_count = ti.xcom_pull(task_ids='collect_artist_ids', key='artist_count')

    if artist_count is None or artist_count == 0:
        log.info("No artists to process, skipping validation")
        return {'status': 'skipped', 'reason': 'no_artists_to_process'}

    # Get results from processing tasks
    artist_details_count = ti.xcom_pull(task_ids='fetch_artist_details', key='artist_details_count')
    kafka_result = ti.xcom_pull(task_ids='publish_to_kafka', key='kafka_result')
    s3_result = ti.xcom_pull(task_ids='save_to_s3', key='s3_result')

    # If any result is None, tasks were skipped
    if artist_details_count is None:
        log.info("Fetch task was skipped, validation not needed")
        return {'status': 'skipped', 'reason': 'fetch_skipped'}

    checks = {}

    # Check Kafka
    if kafka_result and kafka_result['published'] > 0:
        checks['kafka'] = 'PASSED'
        log.info(f"Kafka: {kafka_result['published']} artists published")
    else:
        checks['kafka'] = 'FAILED'
        log.error("Kafka publish failed")

    # Check S3
    if s3_result and s3_result['status'] == 'success':
        checks['s3'] = 'PASSED'
        log.info(f"S3: {s3_result['artists_saved']} artists saved")
    else:
        checks['s3'] = 'FAILED'
        log.error("S3 save failed")

    # Check counts match
    if kafka_result and s3_result:
        if kafka_result['published'] == s3_result['artists_saved'] == artist_details_count:
            checks['count_consistency'] = 'PASSED'
        else:
            checks['count_consistency'] = 'WARNING'
            log.warning(
                f"WARNING: Count mismatch - Fetched: {artist_details_count}, "
                f"Kafka: {kafka_result['published']}, "
                f"S3: {s3_result['artists_saved']}"
            )

    all_passed = all(v == 'PASSED' for v in [checks.get('kafka'), checks.get('s3')])

    if not all_passed:
        raise AirflowException("Validation failed")

    log.info("All validations passed")
    return checks

# ============================================================================ 
# Define DAG
# ============================================================================ 

with DAG(
    dag_id="spotify_artist_ingestion",
    default_args=default_args,
    description="Fetch and store Spotify artist details with deduplication",
    schedule="0 */6 * * *",  # Every 6 hours
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["spotify", "ingestion", "artists"],
) as dag:

    # Collect artist IDs
    collect_task = PythonOperator(
        task_id='collect_artist_ids',
        python_callable=collect_artist_ids_to_fetch,
    )

    # Branch
    branch_task = BranchPythonOperator(
        task_id='check_for_artists',
        python_callable=check_for_artists,
    )

    # Fetch artist details
    fetch_task = PythonOperator(
        task_id='fetch_artist_details',
        python_callable=fetch_artist_details,
    )

    # Publish to Kafka (parallel with S3)
    kafka_task = PythonOperator(
        task_id='publish_to_kafka',
        python_callable=publish_artists_to_kafka,
    )

    # Save to S3 (parallel with Kafka)
    s3_task = PythonOperator(
        task_id='save_to_s3',
        python_callable=save_artists_to_s3,
    )

    # Validate
    validate_task = PythonOperator(
        task_id='validate_outputs',
        python_callable=validate_outputs,
        trigger_rule='all_done',
    )

    # Skip
    skip_task = EmptyOperator(
        task_id='skip_processing',
    )

    # Dependencies
    collect_task >> branch_task
    branch_task >> fetch_task >> [kafka_task, s3_task] >> validate_task
    branch_task >> skip_task
