"""
Upload Google Data Portability exports to MinIO.

Uploads processed JSONL files to MinIO S3-compatible storage,
following the same pattern as Spotify ingestion.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

# MinIO Configuration
# These should match your docker-compose.yml MinIO service
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')

BUCKET_NAME = 'inbound'
S3_PREFIX = 'raw/google'


def get_s3_client():
    """Initialize boto3 S3 client for MinIO"""
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name='us-east-1',  # MinIO doesn't care but boto3 requires it
    )


def ensure_bucket_exists(s3_client):
    """Create inbound bucket if it doesn't exist"""
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"✓ Bucket '{BUCKET_NAME}' exists")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"Creating bucket '{BUCKET_NAME}'...")
            try:
                s3_client.create_bucket(Bucket=BUCKET_NAME)
                print(f"✓ Bucket '{BUCKET_NAME}' created")
                return True
            except Exception as create_error:
                print(f"✗ Failed to create bucket: {create_error}")
                return False
        else:
            print(f"✗ Error checking bucket: {e}")
            return False


def upload_file(s3_client, file_path, resource_name):
    """
    Upload a processed export file to MinIO.

    Args:
        s3_client: boto3 S3 client
        file_path: Local path to the file
        resource_name: Resource name (e.g., 'maps', 'youtube')
    """
    if not os.path.exists(file_path):
        print(f"✗ File not found: {file_path}")
        return False

    filename = os.path.basename(file_path)
    s3_key = f"{S3_PREFIX}/{resource_name}/{filename}"

    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)

    print(f"Uploading {filename} ({file_size_mb:.2f} MB)...")
    print(f"  → s3://{BUCKET_NAME}/{s3_key}")

    try:
        s3_client.upload_file(
            file_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={'ContentType': 'application/gzip'}
        )

        print(f"✓ Upload successful!")
        print(f"  S3 Path: s3://{BUCKET_NAME}/{s3_key}")

        return True

    except Exception as e:
        print(f"✗ Upload failed: {e}")
        return False


def list_uploaded_files(s3_client, resource_name=None):
    """List files in MinIO"""
    prefix = f"{S3_PREFIX}/"
    if resource_name:
        prefix = f"{S3_PREFIX}/{resource_name}/"

    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix
        )

        if 'Contents' in response:
            print(f"\nFiles in s3://{BUCKET_NAME}/{prefix}:")
            for obj in response['Contents']:
                size_mb = obj['Size'] / (1024 * 1024)
                print(f"  - {obj['Key']} ({size_mb:.2f} MB)")
        else:
            print(f"\nNo files found in s3://{BUCKET_NAME}/{prefix}")

    except Exception as e:
        print(f"✗ Error listing files: {e}")


def main():
    """Main upload script"""
    print("=" * 60)
    print("Upload Google Data Portability Exports to MinIO")
    print("=" * 60)
    print()

    # Check for files to upload
    maps_file = "data/processed/google/maps/export_20251201_194500.jsonl.gz"

    if not os.path.exists(maps_file):
        print(f"✗ Processed Maps file not found: {maps_file}")
        print()
        print("Please run the processing script first to generate JSONL files.")
        sys.exit(1)

    print(f"Found processed file:")
    print(f"  - {maps_file}")
    print()

    # Initialize S3 client
    print(f"Connecting to MinIO at {MINIO_ENDPOINT}...")
    try:
        s3_client = get_s3_client()
        # Test connection
        s3_client.list_buckets()
        print("✓ Connected to MinIO")
        print()
    except Exception as e:
        print(f"✗ Failed to connect to MinIO: {e}")
        print()
        print("Please ensure:")
        print("  1. MinIO is running (docker-compose up -d minio)")
        print("  2. MINIO_ENDPOINT is correct (default: http://localhost:9000)")
        print("  3. Credentials are correct (default: minioadmin/minioadmin)")
        print()
        print("You can set these via environment variables:")
        print("  export MINIO_ENDPOINT=http://localhost:9000")
        print("  export MINIO_ACCESS_KEY=minioadmin")
        print("  export MINIO_SECRET_KEY=minioadmin")
        sys.exit(1)

    # Ensure bucket exists
    if not ensure_bucket_exists(s3_client):
        print("✗ Failed to ensure bucket exists")
        sys.exit(1)

    print()

    # Upload Maps file
    success = upload_file(s3_client, maps_file, 'maps')

    if not success:
        sys.exit(1)

    # List uploaded files
    list_uploaded_files(s3_client, 'maps')

    print()
    print("=" * 60)
    print("✓ Upload complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Verify in MinIO UI: http://localhost:9001")
    print("  2. Create ClickHouse bronze table")
    print("  3. Build dbt silver/gold models")
    print()


if __name__ == "__main__":
    main()
