"""
Utility Functions for YouTube Enrichment

Helper functions for ClickHouse queries, data processing, and logging.
"""

import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
import clickhouse_connect

from youtube_enrichment import config

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """
    ClickHouse client for querying video IDs and enriched data.
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None,
    ):
        """
        Initialize ClickHouse client.

        Args:
            host: ClickHouse host
            port: ClickHouse port
            user: Username
            password: Password
            database: Database name
        """
        self.host = host or config.CLICKHOUSE_HOST
        self.port = port or config.CLICKHOUSE_PORT
        self.user = user or config.CLICKHOUSE_USER
        self.password = password or config.CLICKHOUSE_PASSWORD
        self.database = database or config.CLICKHOUSE_DATABASE

        self.client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            database=self.database,
        )

        logger.info(f"Connected to ClickHouse at {self.host}:{self.port}")

    def get_all_video_ids(self) -> List[str]:
        """
        Get all unique video IDs from watch history.

        Returns:
            List of video IDs
        """
        query = """
            SELECT DISTINCT video_id
            FROM silver.silver_youtube_watch_history
            WHERE video_id != ''
            ORDER BY video_id
        """

        try:
            result = self.client.query(query)
            video_ids = [row[0] for row in result.result_rows]
            logger.info(f"Found {len(video_ids)} unique video IDs in watch history")
            return video_ids
        except Exception as e:
            logger.error(f"Error fetching video IDs: {e}")
            return []

    def get_enriched_video_ids(self) -> Set[str]:
        """
        Get set of video IDs that have already been enriched.

        Returns:
            Set of video IDs
        """
        query = """
            SELECT DISTINCT video_id
            FROM bronze.bronze_youtube_video_metadata
            WHERE video_id != ''
        """

        try:
            result = self.client.query(query)
            video_ids = {row[0] for row in result.result_rows}
            logger.info(f"Found {len(video_ids)} already enriched video IDs")
            return video_ids
        except Exception as e:
            # Table might not exist yet
            logger.warning(f"Could not fetch enriched video IDs: {e}")
            return set()

    def get_unenriched_video_ids(self, limit: Optional[int] = None) -> List[str]:
        """
        Get video IDs that need enrichment.

        Args:
            limit: Maximum number of video IDs to return

        Returns:
            List of video IDs needing enrichment
        """
        all_videos = set(self.get_all_video_ids())
        enriched_videos = self.get_enriched_video_ids()

        unenriched = list(all_videos - enriched_videos)

        logger.info(
            f"Found {len(unenriched)} unenriched videos "
            f"(total: {len(all_videos)}, enriched: {len(enriched_videos)})"
        )

        if limit:
            unenriched = unenriched[:limit]
            logger.info(f"Limited to {len(unenriched)} videos")

        return unenriched

    def get_video_watch_counts(self, video_ids: List[str]) -> Dict[str, int]:
        """
        Get watch count for each video ID.

        Used to prioritize frequently watched videos.

        Args:
            video_ids: List of video IDs

        Returns:
            Dictionary mapping video_id -> watch_count
        """
        if not video_ids:
            return {}

        # Create comma-separated quoted list
        video_ids_str = ", ".join([f"'{vid}'" for vid in video_ids])

        query = f"""
            SELECT
                video_id,
                COUNT(*) AS watch_count
            FROM silver.silver_youtube_watch_history
            WHERE video_id IN ({video_ids_str})
            GROUP BY video_id
            ORDER BY watch_count DESC
        """

        try:
            result = self.client.query(query)
            watch_counts = {row[0]: row[1] for row in result.result_rows}
            return watch_counts
        except Exception as e:
            logger.error(f"Error fetching watch counts: {e}")
            return {}

    def close(self):
        """Close ClickHouse connection."""
        if self.client:
            self.client.close()
            logger.info("ClickHouse connection closed")


def batch_list(items: List, batch_size: int):
    """
    Split a list into batches.

    Args:
        items: List to split
        batch_size: Size of each batch

    Yields:
        Batches of items

    Example:
        >>> list(batch_list([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def prioritize_videos(
    video_ids: List[str], watch_counts: Dict[str, int]
) -> List[str]:
    """
    Prioritize videos by watch count (most watched first).

    Args:
        video_ids: List of video IDs
        watch_counts: Dictionary of video_id -> watch_count

    Returns:
        Sorted list of video IDs (most watched first)
    """
    return sorted(video_ids, key=lambda vid: watch_counts.get(vid, 0), reverse=True)


def format_progress(current: int, total: int, prefix: str = "") -> str:
    """
    Format progress string.

    Args:
        current: Current progress
        total: Total items
        prefix: Optional prefix message

    Returns:
        Formatted progress string

    Example:
        >>> format_progress(50, 200, "Processing")
        "Processing: 50/200 (25.0%)"
    """
    if total == 0:
        return f"{prefix}: 0/0 (0%)"

    percentage = (current / total) * 100
    return f"{prefix}: {current}/{total} ({percentage:.1f}%)"


def estimate_time_remaining(
    current: int, total: int, elapsed_seconds: float
) -> str:
    """
    Estimate time remaining based on current progress.

    Args:
        current: Current progress
        total: Total items
        elapsed_seconds: Seconds elapsed so far

    Returns:
        Formatted time remaining string

    Example:
        >>> estimate_time_remaining(100, 1000, 60)
        "~9m remaining"
    """
    if current == 0 or total == 0:
        return "unknown"

    rate = current / elapsed_seconds  # items per second
    remaining = total - current
    seconds_remaining = remaining / rate

    if seconds_remaining < 60:
        return f"~{int(seconds_remaining)}s remaining"
    elif seconds_remaining < 3600:
        return f"~{int(seconds_remaining / 60)}m remaining"
    else:
        hours = int(seconds_remaining / 3600)
        minutes = int((seconds_remaining % 3600) / 60)
        return f"~{hours}h {minutes}m remaining"


class ProgressTracker:
    """
    Track and display enrichment progress.
    """

    def __init__(self, total: int):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
        """
        self.total = total
        self.current = 0
        self.successful = 0
        self.failed = 0
        self.start_time = datetime.now()

    def update(self, count: int = 1, success: bool = True):
        """
        Update progress.

        Args:
            count: Number of items processed
            success: Whether processing was successful
        """
        self.current += count
        if success:
            self.successful += count
        else:
            self.failed += count

    def get_progress_string(self) -> str:
        """
        Get formatted progress string.

        Returns:
            Progress string with stats
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()
        progress = format_progress(self.current, self.total, "Progress")
        time_remaining = estimate_time_remaining(self.current, self.total, elapsed)

        return (
            f"{progress} | "
            f"✓ {self.successful} | "
            f"✗ {self.failed} | "
            f"{time_remaining}"
        )

    def log_progress(self):
        """Log current progress."""
        logger.info(self.get_progress_string())

    def is_complete(self) -> bool:
        """Check if processing is complete."""
        return self.current >= self.total

    def get_summary(self) -> Dict:
        """
        Get summary statistics.

        Returns:
            Dictionary with summary stats
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "total": self.total,
            "processed": self.current,
            "successful": self.successful,
            "failed": self.failed,
            "elapsed_seconds": elapsed,
            "rate_per_second": self.current / elapsed if elapsed > 0 else 0,
        }


def validate_video_metadata(metadata: Dict) -> bool:
    """
    Validate video metadata has required fields.

    Args:
        metadata: Video metadata dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "video_id",
        "channel_id",
        "channel_title",
        "duration_seconds",
        "category_id",
        "category_name",
    ]

    for field in required_fields:
        if field not in metadata or metadata[field] is None:
            logger.warning(f"Missing required field: {field}")
            return False

    return True


def sanitize_for_json(data: Dict) -> Dict:
    """
    Sanitize data for JSON serialization.

    Handles datetime objects and other non-JSON-serializable types.

    Args:
        data: Dictionary to sanitize

    Returns:
        Sanitized dictionary
    """
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            sanitized[key] = value.isoformat()
        elif value is None:
            sanitized[key] = None
        else:
            sanitized[key] = value
    return sanitized
