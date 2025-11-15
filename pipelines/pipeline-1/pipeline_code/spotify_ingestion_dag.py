# dags/spotify_raw_ingestion_jsonl.py
from __future__ import annotations

import io
import json
import gzip
import logging
from datetime import timedelta
from typing import Dict, List

import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.exceptions import AirflowException
from kafka import KafkaProducer
from kafka.errors import KafkaError

from spotify.spotify_api import get_spotify_client, get_recently_played_tracks

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BUCKET_NAME = "inbound"
RAW_FILE_FOLDER = "raw/spotify/api/tracks"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "spotify.tracks.raw"
KAFKA_ARTIST_IDS_TOPIC = "spotify.artist_ids"



default_args = {
    'owner': 'data-engineering',
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'execution_timeout': timedelta(minutes=10),
}

# ============================================================================
# Task 1: Extract RAW from Spotify API
# ============================================================================

def extract_raw_spotify_data(**context):
    """
    Extract raw JSON response from Spotify API.
    - For scheduled runs, uses the execution_date as the 'after' timestamp.
    - For manual runs, fetches the last 50 tracks.
    """
    execution_date = context['execution_date']
    run_id = context['run_id']
    ti = context['task_instance']
    
    sp = get_spotify_client()
    
    # Handle manual vs. scheduled runs
    if run_id and run_id.startswith("manual__"):
        log.info("Manual run detected. Fetching last 50 played tracks.")
        # For manual runs, get the most recent 50 tracks
        raw_response = get_recently_played_tracks(sp)
    else:
        # For scheduled runs, use the execution date window
        after_timestamp = int(execution_date.timestamp() * 1000)
        log.info(f"Scheduled run. Extracting data after: {execution_date}")
        raw_response = get_recently_played_tracks(sp, after=after_timestamp)

    if not raw_response or not raw_response.get('items'):
        log.info("No items returned from API")
        ti.xcom_push(key='raw_items', value=[])
        ti.xcom_push(key='item_count', value=0)
        return 0
    
    items = raw_response.get('items', [])
    
    # Add minimal ingestion metadata to EACH item
    items_with_metadata = []
    for item in items:
        raw_item = {
            'raw_item': item,  # Untouched API response
            '_ingestion_metadata': {
                'ingested_at': pendulum.now('UTC').isoformat(),
                'execution_date': execution_date.isoformat(),
                'dag_id': context['dag'].dag_id,
                'run_id': run_id,
                'source': 'spotify_api',
            }
        }
        items_with_metadata.append(raw_item)
    
    log.info(f"Extracted {len(items_with_metadata)} raw items")
    
    # Push to XCom
    ti.xcom_push(key='raw_items', value=items_with_metadata)
    ti.xcom_push(key='item_count', value=len(items_with_metadata))
    
    return len(items_with_metadata)

# ============================================================================
# Task 2: Branch - Skip if No Data
# ============================================================================

def check_for_data(**context):
    """Branch: Skip processing if no data"""
    ti = context['task_instance']
    item_count = ti.xcom_pull(task_ids='extract_raw_data', key='item_count')

    if item_count == 0:
        log.info("No data to save, skipping")
        return 'skip_processing'
    else:
        log.info(f"Found {item_count} items, proceeding")
        return ['consolidate_to_jsonl', 'publish_to_kafka', 'publish_artist_ids']

# ============================================================================
# Task 3: Consolidate to Daily JSONL
# ============================================================================

def consolidate_raw_to_jsonl(**context):
    """
    Append raw items to daily JSONL file in S3.
    - Groups by date (from played_at)
    - Appends to existing file if exists
    - Deduplicates based on played_at
    - Compresses with gzip
    """
    ti = context['task_instance']
    execution_date = context['execution_date']
    s3_hook = S3Hook(aws_conn_id="minio_s3")
    
    raw_items = ti.xcom_pull(task_ids='extract_raw_data', key='raw_items')
    
    if not raw_items:
        log.info("No items to consolidate")
        return {'status': 'skipped'}
    
    log.info(f"Consolidating {len(raw_items)} items into daily JSONL files...")
    
    # Group items by date (from played_at in raw item)
    from collections import defaultdict
    import pendulum
    
    items_by_date = defaultdict(list)
    
    for item in raw_items:
        try:
            played_at_str = item['raw_item']['played_at']
            played_at_dt = pendulum.parse(played_at_str)
            date_key = played_at_dt.format('YYYY-MM-DD')
            items_by_date[date_key].append(item)
        except Exception as e:
            log.error(f"Failed to parse date from item: {e}")
            # Fallback to execution_date
            date_key = execution_date.format('YYYY-MM-DD')
            items_by_date[date_key].append(item)
    
    log.info(f"Items grouped into {len(items_by_date)} date(s)")
    
    files_written = []
    
    for date_str, date_items in items_by_date.items():
        # S3 key for this date's JSONL file
        key = f"{RAW_FILE_FOLDER}/{date_str}.jsonl.gz"
        
        log.info(f"Processing {len(date_items)} items for date: {date_str}")
        
        try:
            existing_items = []
            
            # Check if file already exists
            if s3_hook.check_for_key(key, BUCKET_NAME):
                log.info(f"Existing file found at s3://{BUCKET_NAME}/{key}")
                
                # Read existing JSONL
                s3_obj = s3_hook.get_key(key, BUCKET_NAME)
                compressed_data = s3_obj.get()["Body"].read()
                
                # Decompress
                decompressed_data = gzip.decompress(compressed_data)
                
                # Parse each line
                for line in decompressed_data.decode('utf-8').strip().split('\n'):
                    if line:
                        try:
                            existing_items.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            log.warning(f"Failed to parse existing line: {e}")
                            continue
                
                log.info(f"Loaded {len(existing_items)} existing items")
            
            # Combine existing + new items
            all_items = existing_items + date_items
            
            # Deduplicate based on played_at (using raw_item.played_at)
            seen_played_at = set()
            unique_items = []
            
            for item in all_items:
                try:
                    played_at = item['raw_item']['played_at']
                    if played_at not in seen_played_at:
                        seen_played_at.add(played_at)
                        unique_items.append(item)
                except KeyError:
                    # If played_at not found, keep item anyway
                    unique_items.append(item)
            
            dedupe_count = len(all_items) - len(unique_items)
            if dedupe_count > 0:
                log.info(f"Removed {dedupe_count} duplicate items")
            
            log.info(f"Total unique items for {date_str}: {len(unique_items)}")
            
            # Write to JSONL format (one JSON per line)
            jsonl_lines = []
            for item in unique_items:
                jsonl_lines.append(json.dumps(item, default=str))
            
            jsonl_content = '\n'.join(jsonl_lines)
            
            # Compress with gzip
            compressed = gzip.compress(jsonl_content.encode('utf-8'))
            
            # Upload to S3
            s3_hook.load_bytes(
                compressed,
                key=key,
                bucket_name=BUCKET_NAME,
                replace=True
            )
            
            file_size_kb = len(compressed) / 1024
            compression_ratio = len(jsonl_content) / len(compressed)
            
            files_written.append({
                'date': date_str,
                's3_path': f"s3://{BUCKET_NAME}/{key}",
                'items': len(unique_items),
                'file_size_kb': round(file_size_kb, 2),
                'compression_ratio': round(compression_ratio, 2),
            })
            
            log.info(
                f"Wrote {len(unique_items)} items to {key} "
                f"({file_size_kb:.2f} KB, {compression_ratio:.1f}x compression)"
            )
            
        except Exception as e:
            log.error(f"Failed to process date {date_str}: {e}", exc_info=True)
            raise AirflowException(f"Failed to consolidate data for {date_str}")
    
    result = {
        'status': 'success',
        'files': files_written,
        'total_items': sum(f['items'] for f in files_written),
        'dates_processed': len(files_written),
    }
    
    ti.xcom_push(key='consolidation_result', value=result)
    
    log.info(
        f"Consolidation complete: {result['total_items']} items "
        f"across {result['dates_processed']} file(s)"
    )
    
    return result

# ============================================================================
# Task 4: Publish RAW to Kafka (Parallel)
# ============================================================================

def publish_raw_to_kafka(**context):
    """
    Publish raw items to Kafka.
    Runs in parallel with JSONL consolidation.
    """
    ti = context['task_instance']
    
    raw_items = ti.xcom_pull(task_ids='extract_raw_data', key='raw_items')
    
    if not raw_items:
        log.info("No items to publish to Kafka")
        return {'status': 'skipped', 'published': 0}
    
    log.info(f"Publishing {len(raw_items)} raw items to Kafka...")
    
    # Initialize Kafka producer
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
        for item in raw_items:
            try:
                # Key = played_at (for partitioning)
                key = item['raw_item'].get('played_at', f"unknown_{success_count}")
                
                # Get timestamp
                timestamp_ms = None
                if 'played_at' in item['raw_item']:
                    try:
                        dt = pendulum.parse(item['raw_item']['played_at'])
                        timestamp_ms = int(dt.timestamp() * 1000)
                    except:
                        pass
                
                # Send to Kafka
                producer.send(
                    topic=KAFKA_TOPIC,
                    value=item,  # Send entire raw item with metadata
                    key=key,
                    timestamp_ms=timestamp_ms
                )
                
                success_count += 1
                
            except KafkaError as e:
                error_count += 1
                log.error(f"Failed to publish item: {e}")
                continue
        
        producer.flush(timeout=30)
        
        result = {
            'status': 'success' if error_count == 0 else 'partial_success',
            'topic': KAFKA_TOPIC,
            'published': success_count,
            'failed': error_count,
            'total': len(raw_items),
        }
        
        ti.xcom_push(key='kafka_result', value=result)
        
        log.info(f"Published {success_count}/{len(raw_items)} items to Kafka")
        
        if error_count > len(raw_items) * 0.1:
            raise AirflowException(f"Too many Kafka failures: {error_count}/{len(raw_items)}")
        
        return result
        
    finally:
        producer.close()

# ============================================================================
# Task 5: Extract and Publish Artist IDs (Parallel)
# ============================================================================

def publish_artist_ids(**context):
    """
    Extract unique artist IDs from tracks and publish to Kafka.
    Runs in parallel with track consolidation and publishing.
    """
    ti = context['task_instance']
    execution_date = context['execution_date']

    raw_items = ti.xcom_pull(task_ids='extract_raw_data', key='raw_items')

    if not raw_items:
        log.info("No items to extract artists from")
        return {'status': 'skipped', 'published': 0}

    log.info(f"Extracting artist IDs from {len(raw_items)} tracks...")

    # Extract unique artist IDs
    artist_ids = set()
    for item in raw_items:
        try:
            track = item['raw_item']['track']
            artists = track.get('artists', [])
            for artist in artists:
                artist_id = artist.get('id')
                if artist_id:
                    artist_ids.add(artist_id)
        except Exception as e:
            log.warning(f"Failed to extract artist from item: {e}")
            continue

    log.info(f"Found {len(artist_ids)} unique artist IDs")

    if not artist_ids:
        return {'status': 'skipped', 'published': 0}

    # Publish to Kafka
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
        compression_type='snappy',
    )

    success_count = 0
    error_count = 0

    try:
        for artist_id in artist_ids:
            try:
                message = {
                    'artist_id': artist_id,
                    'discovered_at': pendulum.now('UTC').isoformat(),
                    'source_dag': context['dag'].dag_id,
                    'execution_date': execution_date.isoformat(),
                }

                producer.send(
                    topic=KAFKA_ARTIST_IDS_TOPIC,
                    value=message,
                    key=artist_id,
                )

                success_count += 1

            except KafkaError as e:
                error_count += 1
                log.error(f"Failed to publish artist ID {artist_id}: {e}")
                continue

        producer.flush(timeout=30)

        result = {
            'status': 'success' if error_count == 0 else 'partial_success',
            'topic': KAFKA_ARTIST_IDS_TOPIC,
            'published': success_count,
            'failed': error_count,
            'total': len(artist_ids),
        }

        ti.xcom_push(key='artist_ids_result', value=result)

        log.info(f"Published {success_count}/{len(artist_ids)} artist IDs to Kafka")

        return result

    finally:
        producer.close()

# ============================================================================
# Task 6: Validate
# ============================================================================

def validate_outputs(**context):
    """Validate consolidation and Kafka publishing"""
    ti = context['task_instance']
    
    item_count = ti.xcom_pull(task_ids='extract_raw_data', key='item_count')
    
    # If no data, skip validation
    if item_count == 0:
        log.info("No data extracted, skipping validation.")
        return
        
    consolidation_result = ti.xcom_pull(task_ids='consolidate_to_jsonl', key='consolidation_result')
    kafka_result = ti.xcom_pull(task_ids='publish_to_kafka', key='kafka_result')
    
    checks = {}
    
    # Check S3 consolidation
    if consolidation_result and consolidation_result['status'] == 'success':
        checks['s3_jsonl'] = 'PASSED'
        log.info(f"S3 JSONL: {consolidation_result['total_items']} items in {consolidation_result['dates_processed']} file(s)")
    else:
        checks['s3_jsonl'] = 'FAILED'
        log.error("S3 consolidation failed")
    
    # Check Kafka
    if kafka_result and kafka_result['published'] > 0:
        checks['kafka'] = 'PASSED'
        log.info(f"Kafka: {kafka_result['published']} events")
    else:
        checks['kafka'] = 'FAILED'
        log.error("Kafka publish failed")
    
    # Check counts
    if consolidation_result and kafka_result:
        if consolidation_result['total_items'] == kafka_result['published'] == item_count:
            checks['count_consistency'] = 'PASSED'
        else:
            checks['count_consistency'] = 'WARNING'
            log.warning(
                f"WARNING: Count mismatch - Extracted: {item_count}, "
                f"S3: {consolidation_result['total_items']}, "
                f"Kafka: {kafka_result['published']}"
            )
    
    all_passed = all(v == 'PASSED' for v in [checks.get('s3_jsonl'), checks.get('kafka')])
    
    if not all_passed:
        raise AirflowException("Validation failed")
    
    log.info("All validations passed")
    return checks

# ============================================================================
# Define DAG
# ============================================================================

with DAG(
    dag_id="spotify_raw_ingestion_jsonl",
    default_args=default_args,
    description="Extract RAW Spotify data to daily JSONL files (consolidated)",
    schedule_interval="*/15 * * * *",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=3,
    tags=["spotify", "ingestion", "raw", "jsonl"],
) as dag:
    
    # Extract
    extract_task = PythonOperator(
        task_id='extract_raw_data',
        python_callable=extract_raw_spotify_data,
    )
    
    # Branch
    branch_task = BranchPythonOperator(
        task_id='check_for_data',
        python_callable=check_for_data,
    )
    
    # Consolidate to JSONL (parallel with Kafka)
    consolidate_task = PythonOperator(
        task_id='consolidate_to_jsonl',
        python_callable=consolidate_raw_to_jsonl,
    )
    
    # Publish to Kafka (parallel with consolidation)
    kafka_task = PythonOperator(
        task_id='publish_to_kafka',
        python_callable=publish_raw_to_kafka,
    )

    # Publish Artist IDs (parallel)
    artist_ids_task = PythonOperator(
        task_id='publish_artist_ids',
        python_callable=publish_artist_ids,
    )

    # Validate
    validate_task = PythonOperator(
        task_id='validate_outputs',
        python_callable=validate_outputs,
        trigger_rule='all_done',
    )

    # Skip
    skip_task = DummyOperator(
        task_id='skip_processing',
    )

    # Dependencies
    extract_task >> branch_task
    branch_task >> [consolidate_task, kafka_task, artist_ids_task] >> validate_task
    branch_task >> skip_task