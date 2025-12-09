"""
Storage Module for YouTube Enrichment

Handles writing enriched video metadata to MinIO/S3 in JSONL.gz format.
Follows the same pattern as existing Google Takeout data storage.
"""

import json
import gzip
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from youtube_enrichment import config

logger = logging.getLogger(__name__)


class MinIOStorage:
    """
    MinIO/S3 storage client for enriched video metadata.

    Stores data in the same format as other ingested data:
    - Location: inbound/enriched/youtube/video_metadata/
    - Format: JSONL.gz (one JSON object per line, gzipped)
    - Naming: enrichment_YYYYMMDD_HHMMSS.jsonl.gz
    """

    def __init__(
        self,
        endpoint_url: str = "http://minio:9000",
        access_key: str = "admin",
        secret_key: str = "minio08062013",
        bucket_name: str = "inbound",
    ):
        """
        Initialize MinIO storage client.

        Args:
            endpoint_url: MinIO endpoint URL
            access_key: Access key
            secret_key: Secret key
            bucket_name: Bucket name
        """
        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.base_path = "raw/google/youtube_enriched/video_metadata"

        # Initialize S3 client for MinIO
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        logger.info(f"MinIO storage initialized: {endpoint_url}/{bucket_name}")

    def store_video_metadata(self, metadata_list: List[Dict]) -> str:
        """
        Store list of video metadata to MinIO as JSONL.gz.

        Args:
            metadata_list: List of video metadata dictionaries

        Returns:
            S3 key of stored file

        Raises:
            Exception: If storage fails
        """
        if not metadata_list:
            logger.warning("No metadata to store")
            return None

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"enrichment_{timestamp}.jsonl.gz"
        s3_key = f"{self.base_path}/{filename}"

        # Create JSONL content
        jsonl_content = "\n".join([json.dumps(record) for record in metadata_list])

        # Compress with gzip
        compressed_content = gzip.compress(jsonl_content.encode("utf-8"))

        # Upload to MinIO
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=compressed_content,
                ContentType="application/gzip",
                Metadata={
                    "record_count": str(len(metadata_list)),
                    "created_at": datetime.now().isoformat(),
                },
            )

            logger.info(
                f"Successfully stored {len(metadata_list)} records to "
                f"s3://{self.bucket_name}/{s3_key}"
            )
            return s3_key

        except ClientError as e:
            logger.error(f"Failed to store metadata to MinIO: {e}")
            raise

    def store_batch(
        self, metadata_list: List[Dict], batch_number: int, total_batches: int
    ) -> str:
        """
        Store a batch of video metadata with batch information.

        Args:
            metadata_list: List of video metadata dictionaries
            batch_number: Current batch number
            total_batches: Total number of batches

        Returns:
            S3 key of stored file
        """
        if not metadata_list:
            return None

        # Generate filename with batch info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"enrichment_{timestamp}_batch{batch_number}of{total_batches}.jsonl.gz"
        s3_key = f"{self.base_path}/{filename}"

        # Create JSONL content
        jsonl_content = "\n".join([json.dumps(record) for record in metadata_list])

        # Compress with gzip
        compressed_content = gzip.compress(jsonl_content.encode("utf-8"))

        # Upload to MinIO
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=compressed_content,
                ContentType="application/gzip",
                Metadata={
                    "record_count": str(len(metadata_list)),
                    "batch_number": str(batch_number),
                    "total_batches": str(total_batches),
                    "created_at": datetime.now().isoformat(),
                },
            )

            logger.info(
                f"Successfully stored batch {batch_number}/{total_batches} "
                f"({len(metadata_list)} records) to s3://{self.bucket_name}/{s3_key}"
            )
            return s3_key

        except ClientError as e:
            logger.error(f"Failed to store batch to MinIO: {e}")
            raise

    def list_enriched_files(self) -> List[str]:
        """
        List all enriched video metadata files in MinIO.

        Returns:
            List of S3 keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=self.base_path
            )

            if "Contents" not in response:
                return []

            files = [obj["Key"] for obj in response["Contents"]]
            logger.info(f"Found {len(files)} enriched files in MinIO")
            return files

        except ClientError as e:
            logger.error(f"Failed to list files from MinIO: {e}")
            return []

    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in MinIO.

        Args:
            s3_key: S3 key to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False


class LocalStorage:
    """
    Local file storage for testing/development.

    Stores enriched data locally before uploading to MinIO.
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize local storage.

        Args:
            output_dir: Directory to store files
        """
        self.output_dir = output_dir or config.ENRICHED_DATA_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Local storage initialized: {self.output_dir}")

    def store_video_metadata(self, metadata_list: List[Dict]) -> Path:
        """
        Store video metadata to local JSONL.gz file.

        Args:
            metadata_list: List of video metadata dictionaries

        Returns:
            Path to stored file
        """
        if not metadata_list:
            logger.warning("No metadata to store")
            return None

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"enrichment_{timestamp}.jsonl.gz"
        filepath = self.output_dir / filename

        # Create JSONL content
        jsonl_content = "\n".join([json.dumps(record) for record in metadata_list])

        # Compress and write
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            f.write(jsonl_content)

        logger.info(
            f"Successfully stored {len(metadata_list)} records to {filepath}"
        )
        return filepath

    def store_batch(
        self, metadata_list: List[Dict], batch_number: int, total_batches: int
    ) -> Path:
        """
        Store a batch to local file.

        Args:
            metadata_list: List of video metadata dictionaries
            batch_number: Current batch number
            total_batches: Total number of batches

        Returns:
            Path to stored file
        """
        if not metadata_list:
            return None

        # Generate filename with batch info
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"enrichment_{timestamp}_batch{batch_number}of{total_batches}.jsonl.gz"
        filepath = self.output_dir / filename

        # Create JSONL content
        jsonl_content = "\n".join([json.dumps(record) for record in metadata_list])

        # Compress and write
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            f.write(jsonl_content)

        logger.info(
            f"Successfully stored batch {batch_number}/{total_batches} "
            f"({len(metadata_list)} records) to {filepath}"
        )
        return filepath

    def list_files(self) -> List[Path]:
        """
        List all local enriched files.

        Returns:
            List of file paths
        """
        files = list(self.output_dir.glob("enrichment_*.jsonl.gz"))
        logger.info(f"Found {len(files)} enriched files locally")
        return files


def create_storage(use_local: bool = False) -> MinIOStorage | LocalStorage:
    """
    Factory function to create storage client.

    Args:
        use_local: If True, use local storage. Otherwise use MinIO.

    Returns:
        Storage client instance
    """
    if use_local:
        return LocalStorage()
    else:
        return MinIOStorage()
