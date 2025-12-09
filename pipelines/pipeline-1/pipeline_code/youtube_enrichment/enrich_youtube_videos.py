#!/usr/bin/env python3
"""
YouTube Video Enrichment Script

Enriches YouTube watch history with channel information, video metadata,
and watch time estimates using the YouTube Data API v3.

Usage:
    # Process first 100 videos
    python -m youtube_enrichment.enrich_youtube_videos --limit 100

    # Dry run (see what would be processed)
    python -m youtube_enrichment.enrich_youtube_videos --dry-run

    # Use local storage instead of MinIO
    python -m youtube_enrichment.enrich_youtube_videos --local

    # Process all unenriched videos
    python -m youtube_enrichment.enrich_youtube_videos
"""

import sys
import argparse
import logging
from datetime import datetime
from typing import List, Dict

from youtube_enrichment import config
from youtube_enrichment.youtube_api_client import create_client
from youtube_enrichment.utils import (
    ClickHouseClient,
    batch_list,
    prioritize_videos,
    ProgressTracker,
    validate_video_metadata,
    sanitize_for_json,
)
from youtube_enrichment.storage import create_storage

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE) if config.LOG_FILE.parent.exists() else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)


class YouTubeEnricher:
    """
    Main enrichment orchestrator.
    """

    def __init__(
        self,
        youtube_client,
        clickhouse_client,
        storage_client,
        dry_run: bool = False,
    ):
        """
        Initialize enricher.

        Args:
            youtube_client: YouTube API client
            clickhouse_client: ClickHouse client
            storage_client: Storage client (MinIO or local)
            dry_run: If True, don't actually enrich or store data
        """
        self.youtube = youtube_client
        self.ch = clickhouse_client
        self.storage = storage_client
        self.dry_run = dry_run

        logger.info(f"YouTube Enricher initialized (dry_run={dry_run})")

    def get_videos_to_enrich(self, limit: int = None, prioritize: bool = True) -> List[str]:
        """
        Get list of video IDs that need enrichment.

        Args:
            limit: Maximum number of videos to process
            prioritize: If True, prioritize by watch count

        Returns:
            List of video IDs
        """
        logger.info("Fetching videos that need enrichment...")

        # Get unenriched video IDs
        video_ids = self.ch.get_unenriched_video_ids(limit=limit)

        if not video_ids:
            logger.info("No videos need enrichment!")
            return []

        # Optionally prioritize by watch count
        if prioritize and len(video_ids) > 0:
            logger.info("Prioritizing videos by watch count...")
            watch_counts = self.ch.get_video_watch_counts(video_ids)
            video_ids = prioritize_videos(video_ids, watch_counts)

        logger.info(f"Found {len(video_ids)} videos to enrich")
        return video_ids

    def enrich_batch(self, video_ids: List[str]) -> List[Dict]:
        """
        Enrich a batch of video IDs.

        Args:
            video_ids: List of video IDs (max 50)

        Returns:
            List of enriched video metadata
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would enrich {len(video_ids)} videos")
            return []

        # Call YouTube API
        try:
            metadata_list = self.youtube.get_video_metadata(video_ids)

            # Validate and sanitize
            valid_metadata = []
            for metadata in metadata_list:
                if validate_video_metadata(metadata):
                    sanitized = sanitize_for_json(metadata)
                    valid_metadata.append(sanitized)
                else:
                    logger.warning(f"Invalid metadata for video {metadata.get('video_id')}")

            return valid_metadata

        except Exception as e:
            logger.error(f"Error enriching batch: {e}")
            return []

    def store_batch(
        self, metadata_list: List[Dict], batch_number: int, total_batches: int
    ) -> bool:
        """
        Store enriched metadata.

        Args:
            metadata_list: List of video metadata
            batch_number: Current batch number
            total_batches: Total number of batches

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would store {len(metadata_list)} records")
            return True

        if not metadata_list:
            return False

        try:
            self.storage.store_batch(metadata_list, batch_number, total_batches)
            return True
        except Exception as e:
            logger.error(f"Error storing batch: {e}")
            return False

    def run(self, limit: int = None) -> Dict:
        """
        Run the enrichment process.

        Args:
            limit: Maximum number of videos to process

        Returns:
            Summary statistics
        """
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info("Starting YouTube Video Enrichment")
        logger.info("=" * 60)

        # Get videos to enrich
        video_ids = self.get_videos_to_enrich(limit=limit)

        if not video_ids:
            logger.info("Nothing to enrich!")
            return {"status": "nothing_to_enrich", "processed": 0}

        # Check quota
        quota_info = self.youtube.get_quota_usage()
        logger.info(
            f"Quota: {quota_info['used']}/{quota_info['limit']} "
            f"({quota_info['remaining']} remaining)"
        )

        # Calculate batches
        batches = list(batch_list(video_ids, config.YOUTUBE_BATCH_SIZE))
        total_batches = len(batches)

        logger.info(f"Processing {len(video_ids)} videos in {total_batches} batches")

        # Check if we have enough quota
        if quota_info['remaining'] < total_batches:
            logger.warning(
                f"Not enough quota! Need {total_batches} units, "
                f"have {quota_info['remaining']}"
            )
            if not self.dry_run:
                logger.error("Aborting to avoid quota exhaustion")
                return {"status": "quota_exceeded", "processed": 0}

        # Initialize progress tracker
        progress = ProgressTracker(len(video_ids))

        # Process batches
        successful_videos = 0
        failed_videos = 0

        for batch_number, batch in enumerate(batches, start=1):
            logger.info(f"\nProcessing batch {batch_number}/{total_batches}...")

            # Enrich batch
            metadata_list = self.enrich_batch(batch)

            if metadata_list:
                # Store batch
                if self.store_batch(metadata_list, batch_number, total_batches):
                    successful_videos += len(metadata_list)
                    progress.update(len(metadata_list), success=True)
                else:
                    failed_videos += len(metadata_list)
                    progress.update(len(metadata_list), success=False)
            else:
                # Enrichment failed for entire batch
                failed_videos += len(batch)
                progress.update(len(batch), success=False)

            # Log progress
            progress.log_progress()

            # Check quota after each batch
            quota_info = self.youtube.get_quota_usage()
            if quota_info['remaining'] < 10:
                logger.warning("Running low on quota, stopping...")
                break

        # Final summary
        elapsed = (datetime.now() - start_time).total_seconds()
        quota_info = self.youtube.get_quota_usage()

        logger.info("\n" + "=" * 60)
        logger.info("Enrichment Complete!")
        logger.info("=" * 60)
        logger.info(f"Total videos processed: {successful_videos + failed_videos}")
        logger.info(f"✓ Successful: {successful_videos}")
        logger.info(f"✗ Failed: {failed_videos}")
        logger.info(f"Time elapsed: {elapsed:.1f}s")
        logger.info(f"Rate: {(successful_videos + failed_videos) / elapsed:.2f} videos/sec")
        logger.info(
            f"Quota used: {quota_info['used']}/{quota_info['limit']} "
            f"({quota_info['remaining']} remaining)"
        )

        return {
            "status": "success",
            "processed": successful_videos + failed_videos,
            "successful": successful_videos,
            "failed": failed_videos,
            "elapsed_seconds": elapsed,
            "quota_used": quota_info['used'],
            "quota_remaining": quota_info['remaining'],
        }


def main():
    """
    Main entry point.
    """
    parser = argparse.ArgumentParser(
        description="Enrich YouTube watch history with video metadata"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of videos to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate enrichment without making API calls or storing data",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Store data locally instead of MinIO",
    )
    parser.add_argument(
        "--no-prioritize",
        action="store_true",
        help="Don't prioritize videos by watch count",
    )

    args = parser.parse_args()

    # Validate configuration
    if not config.validate_config():
        logger.error("Configuration validation failed. See errors above.")
        sys.exit(1)

    try:
        # Initialize clients
        logger.info("Initializing clients...")
        youtube_client = create_client()
        ch_client = ClickHouseClient()
        storage_client = create_storage(use_local=args.local)

        # Create enricher
        enricher = YouTubeEnricher(
            youtube_client=youtube_client,
            clickhouse_client=ch_client,
            storage_client=storage_client,
            dry_run=args.dry_run,
        )

        # Run enrichment
        summary = enricher.run(limit=args.limit)

        # Close connections
        ch_client.close()

        # Exit with appropriate code
        if summary["status"] == "success":
            sys.exit(0)
        elif summary["status"] == "nothing_to_enrich":
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nEnrichment interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
