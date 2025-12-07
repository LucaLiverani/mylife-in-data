# dags/google_export_monitor_dag.py
"""
Google Data Portability Export Monitor & Processor DAG

Monitors pending export jobs, downloads completed exports,
processes them, and saves to MinIO + Kafka (like Spotify pattern).

Run: Every 30 minutes
"""
from __future__ import annotations

import io
import os
import json
import gzip
import shutil
import zipfile
import logging
import tempfile
from datetime import timedelta
from typing import Dict, List, Optional

import pendulum
from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.providers.standard.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.exceptions import AirflowException, AirflowSkipException
from kafka import KafkaProducer
from kafka.errors import KafkaError

from google_data_portability.data_portability_api import get_client_local

log = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BUCKET_NAME = "inbound"
RAW_FILE_FOLDER = "raw/google"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"

# Use absolute paths relative to this DAG file
import os as _os
DAG_DIR = _os.path.dirname(__file__)
CLIENT_SECRETS_PATH = _os.path.join(DAG_DIR, 'client_secrets.json')
TOKEN_CACHE_PATH = _os.path.join(DAG_DIR, 'tokens', '.google_portability_token.pickle')

# Minimum age before checking job (avoid premature checks)
MIN_JOB_AGE_MINUTES = 5

default_args = {
    'owner': 'data-engineering',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

# ============================================================================
# Task 1: Get Pending Jobs
# ============================================================================

def get_pending_jobs(**context):
    """
    Retrieve pending export jobs from Airflow Variables.
    Filters out jobs that are too young to check.
    """
    ti = context['task_instance']

    try:
        jobs_json = Variable.get('google_portability_pending_jobs', default_var='[]')
        all_jobs = json.loads(jobs_json)
    except Exception as e:
        log.error(f"Failed to load pending jobs: {e}")
        all_jobs = []

    if not all_jobs:
        log.info("No pending jobs found")
        ti.xcom_push(key='pending_jobs', value=[])
        ti.xcom_push(key='job_count', value=0)
        return 0

    # Filter jobs by age (skip very recent ones)
    now = pendulum.now('UTC')
    min_age = timedelta(minutes=MIN_JOB_AGE_MINUTES)

    eligible_jobs = []
    for job in all_jobs:
        initiated_at = pendulum.parse(job['initiated_at'])
        age = now - initiated_at

        if age >= min_age:
            eligible_jobs.append(job)
        else:
            log.info(f"Skipping job {job['job_id']} (too young: {age.total_seconds():.0f}s)")

    log.info(f"Found {len(eligible_jobs)} eligible job(s) (out of {len(all_jobs)} total)")

    ti.xcom_push(key='pending_jobs', value=eligible_jobs)
    ti.xcom_push(key='job_count', value=len(eligible_jobs))

    return len(eligible_jobs)

# ============================================================================
# Task 2: Branch - Skip if No Jobs
# ============================================================================

def branch_check_jobs(**context):
    """Branch: Skip if no eligible jobs"""
    ti = context['task_instance']
    job_count = ti.xcom_pull(task_ids='get_pending_jobs', key='job_count')

    if job_count == 0:
        log.info("No jobs to process, skipping")
        return 'skip_processing'
    else:
        log.info(f"Found {job_count} job(s) to check")
        return 'check_job_status'

# ============================================================================
# Task 3: Check Job Status
# ============================================================================

def check_job_status(**context):
    """
    Check status of all pending jobs.
    Returns list of completed jobs ready for download.
    """
    ti = context['task_instance']

    pending_jobs = ti.xcom_pull(task_ids='get_pending_jobs', key='pending_jobs')

    if not pending_jobs:
        raise AirflowSkipException("No jobs to check")

    log.info(f"Checking status of {len(pending_jobs)} job(s)...")

    # Initialize client
    client = get_client_local(
        scopes=['youtube_activity', 'maps_activity'],
        client_secrets_file=CLIENT_SECRETS_PATH,
        token_cache_path=TOKEN_CACHE_PATH
    )

    completed_jobs = []
    still_pending_jobs = []
    failed_jobs = []

    for job in pending_jobs:
        job_id = job['job_id']
        resource = job['resource']

        try:
            # Check status
            state = client.get_archive_state(job_id)
            job_state = state.get('state', 'UNKNOWN')

            log.info(f"Job {job_id} ({resource}): {job_state}")

            # Update job metadata
            job['status'] = job_state
            job['last_checked'] = pendulum.now('UTC').isoformat()

            if job_state == 'COMPLETE':
                # Add download URLs
                job['download_urls'] = state.get('urls', [])
                completed_jobs.append(job)
                log.info(f"  ✓ Job complete! {len(job['download_urls'])} file(s) ready")

            elif job_state in ['IN_PROGRESS', 'INITIATED']:
                still_pending_jobs.append(job)
                log.info(f"  ⏳ Still processing...")

            elif job_state == 'FAILED':
                failed_jobs.append(job)
                log.error(f"  ✗ Job failed")

            else:
                log.warning(f"  Unknown state: {job_state}")
                still_pending_jobs.append(job)

        except Exception as e:
            log.error(f"Error checking job {job_id}: {e}")
            still_pending_jobs.append(job)

    # Update pending jobs (remove completed/failed, keep in-progress)
    Variable.set('google_portability_pending_jobs', json.dumps(still_pending_jobs))

    log.info(f"Status summary:")
    log.info(f"  Complete: {len(completed_jobs)}")
    log.info(f"  In Progress: {len(still_pending_jobs)}")
    log.info(f"  Failed: {len(failed_jobs)}")

    # Push results
    ti.xcom_push(key='completed_jobs', value=completed_jobs)
    ti.xcom_push(key='completed_count', value=len(completed_jobs))

    return {
        'completed': len(completed_jobs),
        'pending': len(still_pending_jobs),
        'failed': len(failed_jobs),
    }

# ============================================================================
# Task 4: Branch - Process if Complete
# ============================================================================

def branch_process_completed(**context):
    """Branch: Process if we have completed jobs"""
    ti = context['task_instance']
    completed_count = ti.xcom_pull(task_ids='check_job_status', key='completed_count')

    if completed_count == 0:
        log.info("No completed jobs, skipping processing")
        return 'skip_processing'
    else:
        log.info(f"Processing {completed_count} completed job(s)")
        return 'download_and_extract'

# ============================================================================
# Task 5: Download and Extract
# ============================================================================

def download_and_extract(**context):
    """
    Download completed exports and extract JSON files.
    """
    ti = context['task_instance']

    completed_jobs = ti.xcom_pull(task_ids='check_job_status', key='completed_jobs')

    if not completed_jobs:
        raise AirflowSkipException("No completed jobs to download")

    # Initialize client
    client = get_client_local(
        scopes=['youtube_activity', 'maps_activity'],
        client_secrets_file=CLIENT_SECRETS_PATH,
        token_cache_path=TOKEN_CACHE_PATH
    )

    extracted_data = []

    for job in completed_jobs:
        job_id = job['job_id']
        resource = job['resource']
        urls = job['download_urls']

        log.info(f"Downloading export for {resource} ({len(urls)} file(s))...")

        # Create temp directory for this job
        temp_dir = tempfile.mkdtemp(prefix=f'google_export_{job_id}_')

        try:
            # Download all files
            all_json_data = []

            for idx, url in enumerate(urls, 1):
                zip_path = os.path.join(temp_dir, f'part_{idx}.zip')

                log.info(f"  [{idx}/{len(urls)}] Downloading...")
                client.download_archive_file(url, zip_path)

                # Extract ZIP
                extract_dir = os.path.join(temp_dir, f'extracted_{idx}')
                os.makedirs(extract_dir, exist_ok=True)

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                # Find JSON files (usually in Portability/My Activity/*/MyActivity.json)
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if file.endswith('.json'):
                            json_path = os.path.join(root, file)
                            log.info(f"  Found JSON: {json_path}")

                            with open(json_path, 'r') as f:
                                data = json.load(f)

                            # Combine if multiple files
                            if isinstance(data, list):
                                all_json_data.extend(data)
                            else:
                                all_json_data.append(data)

            log.info(f"✓ Downloaded and extracted {len(all_json_data)} record(s)")

            extracted_data.append({
                'job_id': job_id,
                'resource': resource,
                'data': all_json_data,
                'record_count': len(all_json_data),
                'temp_dir': temp_dir,
            })

        except Exception as e:
            log.error(f"Failed to download/extract job {job_id}: {e}")
            # Cleanup temp dir
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise AirflowException(f"Download failed for {job_id}: {e}")

    ti.xcom_push(key='extracted_data', value=extracted_data)

    return {
        'jobs_processed': len(extracted_data),
        'total_records': sum(ed['record_count'] for ed in extracted_data),
    }

# ============================================================================
# Task 6: Process Exports
# ============================================================================

def process_exports(**context):
    """
    Process extracted exports into JSONL format with metadata.
    Similar to Spotify pattern but for bulk exports.
    """
    ti = context['task_instance']
    logical_date = context.get('logical_date') or pendulum.now('UTC')

    extracted_data = ti.xcom_pull(task_ids='download_and_extract', key='extracted_data')

    if not extracted_data:
        raise AirflowSkipException("No data to process")

    processed_files = []

    for export in extracted_data:
        job_id = export['job_id']
        resource = export['resource']
        data = export['data']
        record_count = export['record_count']

        log.info(f"Processing {resource} export ({record_count} records)...")

        # Export metadata
        export_metadata = {
            'export_timestamp': pendulum.now('UTC').isoformat(),
            'export_job_id': job_id,
            'export_date': logical_date.format('YYYY-MM-DD'),
            'source': 'google_data_portability_api',
            'resource': resource,
            'record_count': record_count,
            'dag_id': context['dag'].dag_id,
            'run_id': context['run_id'],
        }

        # Transform to JSONL
        jsonl_lines = []
        for item in data:
            enriched_item = {
                'activity': item,  # Original activity data
                '_export_metadata': export_metadata,
            }
            jsonl_lines.append(json.dumps(enriched_item, default=str))

        jsonl_content = '\n'.join(jsonl_lines)

        # Compress
        compressed = gzip.compress(jsonl_content.encode('utf-8'))

        # Generate filename
        resource_name = resource.split('.')[-1]  # e.g., 'youtube' or 'maps'
        timestamp = logical_date.format('YYYYMMdd_HHmmss')
        filename = f"export_{timestamp}_{job_id[:8]}.jsonl.gz"

        # Save to temp file
        temp_file = os.path.join(export['temp_dir'], filename)
        with open(temp_file, 'wb') as f:
            f.write(compressed)

        compression_ratio = len(jsonl_content) / len(compressed)

        log.info(f"✓ Processed {resource_name} export:")
        log.info(f"    Records: {record_count}")
        log.info(f"    Original size: {len(jsonl_content):,} bytes")
        log.info(f"    Compressed size: {len(compressed):,} bytes")
        log.info(f"    Compression: {compression_ratio:.1f}x")

        processed_files.append({
            'job_id': job_id,
            'resource': resource,
            'resource_name': resource_name,
            'filename': filename,
            'file_path': temp_file,
            'record_count': record_count,
            'compressed_size': len(compressed),
            'temp_dir': export['temp_dir'],
        })

    ti.xcom_push(key='processed_files', value=processed_files)

    return {
        'files_processed': len(processed_files),
        'total_records': sum(pf['record_count'] for pf in processed_files),
    }

# ============================================================================
# Task 7: Upload to MinIO
# ============================================================================

def upload_to_minio(**context):
    """
    Upload processed files to MinIO.
    Pattern: s3://inbound/raw/google/{service}/export_*.jsonl.gz
    """
    ti = context['task_instance']

    processed_files = ti.xcom_pull(task_ids='process_exports', key='processed_files')

    if not processed_files:
        raise AirflowSkipException("No files to upload")

    s3_hook = S3Hook(aws_conn_id="minio_s3")

    uploaded_files = []

    for file_info in processed_files:
        resource_name = file_info['resource_name']
        filename = file_info['filename']
        file_path = file_info['file_path']

        # S3 key
        key = f"{RAW_FILE_FOLDER}/{resource_name}/{filename}"

        log.info(f"Uploading {filename} to MinIO...")

        try:
            with open(file_path, 'rb') as f:
                s3_hook.load_file_obj(
                    f,
                    key=key,
                    bucket_name=BUCKET_NAME,
                    replace=True
                )

            s3_path = f"s3://{BUCKET_NAME}/{key}"
            log.info(f"  ✓ Uploaded to {s3_path}")

            uploaded_files.append({
                'job_id': file_info['job_id'],
                'resource': file_info['resource'],
                's3_path': s3_path,
                'record_count': file_info['record_count'],
            })

        except Exception as e:
            log.error(f"Failed to upload {filename}: {e}")
            raise AirflowException(f"MinIO upload failed: {e}")

    ti.xcom_push(key='uploaded_files', value=uploaded_files)

    return {
        'files_uploaded': len(uploaded_files),
        's3_paths': [uf['s3_path'] for uf in uploaded_files],
    }

# ============================================================================
# Task 8: Publish to Kafka (Parallel)
# ============================================================================

def publish_to_kafka(**context):
    """
    Publish records to Kafka for real-time processing.
    Runs in parallel with MinIO upload.
    """
    ti = context['task_instance']

    processed_files = ti.xcom_pull(task_ids='process_exports', key='processed_files')

    if not processed_files:
        raise AirflowSkipException("No data to publish")

    # Initialize Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
        compression_type='snappy',
    )

    total_published = 0
    total_failed = 0

    try:
        for file_info in processed_files:
            resource_name = file_info['resource_name']
            file_path = file_info['file_path']

            # Determine Kafka topic
            topic = f"google.{resource_name}.raw"

            log.info(f"Publishing {resource_name} records to Kafka topic: {topic}")

            # Read compressed JSONL
            with gzip.open(file_path, 'rt') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        record = json.loads(line)

                        # Key = activity timestamp if available
                        key = None
                        if 'activity' in record and 'time' in record['activity']:
                            key = record['activity']['time']

                        # Send to Kafka
                        producer.send(
                            topic=topic,
                            value=record,
                            key=key,
                        )

                        total_published += 1

                        if line_num % 1000 == 0:
                            log.info(f"  Published {line_num} records...")

                    except Exception as e:
                        total_failed += 1
                        log.error(f"Failed to publish record {line_num}: {e}")
                        continue

            log.info(f"✓ Published {line_num} records to {topic}")

        producer.flush(timeout=60)

        result = {
            'status': 'success' if total_failed == 0 else 'partial_success',
            'published': total_published,
            'failed': total_failed,
        }

        ti.xcom_push(key='kafka_result', value=result)

        log.info(f"Kafka publish complete: {total_published} records")

        if total_failed > total_published * 0.1:
            raise AirflowException(f"Too many Kafka failures: {total_failed}")

        return result

    finally:
        producer.close()

# ============================================================================
# Task 9: Cleanup
# ============================================================================

def cleanup_temp_files(**context):
    """
    Cleanup temporary files and directories.
    """
    ti = context['task_instance']

    processed_files = ti.xcom_pull(task_ids='process_exports', key='processed_files')

    if not processed_files:
        log.info("No temp files to cleanup")
        return

    for file_info in processed_files:
        temp_dir = file_info['temp_dir']

        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                log.info(f"Cleaned up: {temp_dir}")
            except Exception as e:
                log.warning(f"Failed to cleanup {temp_dir}: {e}")

    log.info("✓ Cleanup complete")

# ============================================================================
# Define DAG
# ============================================================================

with DAG(
    dag_id="google_export_monitor",
    default_args=default_args,
    description="Monitor Google exports, download, and process to MinIO + Kafka",
    schedule="*/30 * * * *",  # Every 30 minutes
    start_date=pendulum.datetime(2025, 12, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["google", "data-portability", "export", "monitor"],
) as dag:

    # Get pending jobs
    get_jobs_task = PythonOperator(
        task_id='get_pending_jobs',
        python_callable=get_pending_jobs,
    )

    # Branch: Skip if no jobs
    branch_jobs_task = BranchPythonOperator(
        task_id='branch_check_jobs',
        python_callable=branch_check_jobs,
    )

    # Check job status
    check_status_task = PythonOperator(
        task_id='check_job_status',
        python_callable=check_job_status,
    )

    # Branch: Process if complete
    branch_process_task = BranchPythonOperator(
        task_id='branch_process_completed',
        python_callable=branch_process_completed,
    )

    # Download and extract
    download_task = PythonOperator(
        task_id='download_and_extract',
        python_callable=download_and_extract,
    )

    # Process exports
    process_task = PythonOperator(
        task_id='process_exports',
        python_callable=process_exports,
    )

    # Upload to MinIO (parallel with Kafka)
    upload_task = PythonOperator(
        task_id='upload_to_minio',
        python_callable=upload_to_minio,
    )

    # Publish to Kafka (parallel with MinIO)
    kafka_task = PythonOperator(
        task_id='publish_to_kafka',
        python_callable=publish_to_kafka,
    )

    # Cleanup
    cleanup_task = PythonOperator(
        task_id='cleanup_temp_files',
        python_callable=cleanup_temp_files,
        trigger_rule='all_done',
    )

    # Skip
    skip_task = EmptyOperator(
        task_id='skip_processing',
    )

    # Dependencies
    get_jobs_task >> branch_jobs_task

    # If jobs found
    branch_jobs_task >> check_status_task >> branch_process_task

    # If completed
    branch_process_task >> download_task >> process_task >> [upload_task, kafka_task] >> cleanup_task

    # If no jobs or not complete
    branch_jobs_task >> skip_task
    branch_process_task >> skip_task
