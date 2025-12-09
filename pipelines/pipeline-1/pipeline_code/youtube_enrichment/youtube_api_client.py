"""
YouTube API Client

Wrapper for YouTube Data API v3 with rate limiting, quota management,
and batch processing capabilities.
"""

import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
import isodate

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from youtube_enrichment import config


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


class YouTubeAPIClient:
    """
    YouTube Data API v3 client with quota management and rate limiting.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize YouTube API client.

        Args:
            api_key: YouTube Data API key. If None, will try to load from config.

        Raises:
            ValueError: If no valid API credentials found
        """
        self.api_key = api_key or config.get_api_key()

        if not self.api_key:
            raise ValueError(
                "No YouTube API key found. "
                "Set YOUTUBE_API_KEY environment variable or create credentials file. "
                "See SETUP_GUIDE.md for instructions."
            )

        # Build YouTube API client
        self.youtube = build(
            config.YOUTUBE_API_SERVICE_NAME,
            config.YOUTUBE_API_VERSION,
            developerKey=self.api_key
        )

        # Initialize quota tracker
        self.quota_tracker = config.quota_tracker

        logger.info("YouTube API client initialized successfully")

    def get_video_metadata(self, video_ids: List[str]) -> List[Dict]:
        """
        Get metadata for a list of video IDs.

        Args:
            video_ids: List of YouTube video IDs (max 50 per call)

        Returns:
            List of video metadata dictionaries containing:
                - video_id
                - channel_id
                - channel_title
                - duration_seconds
                - category_id
                - category_name
                - published_at
                - title
                - description (optional)
                - view_count (optional)

        Raises:
            ValueError: If more than 50 video IDs provided
            HttpError: If API request fails
        """
        if len(video_ids) > config.YOUTUBE_BATCH_SIZE:
            raise ValueError(
                f"Maximum {config.YOUTUBE_BATCH_SIZE} video IDs per request. "
                f"Got {len(video_ids)}"
            )

        # Check quota availability
        if not self.quota_tracker.is_available(1):
            logger.warning(
                f"Quota limit reached: {self.quota_tracker.units_used}/"
                f"{self.quota_tracker.limit}"
            )
            return []

        # Filter out empty/None video IDs
        video_ids = [vid for vid in video_ids if vid]

        if not video_ids:
            return []

        try:
            # Rate limiting
            time.sleep(config.RATE_LIMIT_DELAY)

            # Call YouTube API
            logger.info(f"Fetching metadata for {len(video_ids)} videos")
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids)
            )
            response = request.execute()

            # Track quota usage (1 unit per call)
            self.quota_tracker.use_quota(1)

            # Parse response
            results = []
            for item in response.get("items", []):
                video_data = self._parse_video_item(item)
                if video_data:
                    results.append(video_data)

            logger.info(
                f"Successfully fetched metadata for {len(results)} videos. "
                f"Quota used: {self.quota_tracker.units_used}/"
                f"{self.quota_tracker.limit}"
            )

            return results

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            if e.resp.status == 403:
                logger.error("Quota exceeded or API key invalid")
            raise

    def _parse_video_item(self, item: Dict) -> Optional[Dict]:
        """
        Parse a video item from YouTube API response.

        Args:
            item: Video item from API response

        Returns:
            Parsed video metadata dictionary or None if parsing fails
        """
        try:
            video_id = item["id"]
            snippet = item["snippet"]
            content_details = item["contentDetails"]
            statistics = item.get("statistics", {})

            # Parse ISO 8601 duration to seconds
            duration_iso = content_details.get("duration", "PT0S")
            duration_seconds = self.parse_duration_to_seconds(duration_iso)

            # Get category name
            category_id = snippet.get("categoryId", "0")
            category_name = config.get_category_name(category_id)

            return {
                "video_id": video_id,
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "duration_seconds": duration_seconds,
                "category_id": category_id,
                "category_name": category_name,
                "published_at": snippet.get("publishedAt"),
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "comment_count": int(statistics.get("commentCount", 0)),
                "enriched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error parsing video item: {e}")
            return None

    @staticmethod
    def parse_duration_to_seconds(iso_duration: str) -> int:
        """
        Convert ISO 8601 duration to seconds.

        Args:
            iso_duration: Duration string (e.g., "PT15M33S")

        Returns:
            Duration in seconds

        Examples:
            >>> YouTubeAPIClient.parse_duration_to_seconds("PT15M33S")
            933
            >>> YouTubeAPIClient.parse_duration_to_seconds("PT1H2M3S")
            3723
        """
        try:
            duration = isodate.parse_duration(iso_duration)
            return int(duration.total_seconds())
        except Exception as e:
            logger.error(f"Error parsing duration '{iso_duration}': {e}")
            return 0

    def get_channel_metadata(self, channel_ids: List[str]) -> List[Dict]:
        """
        Get metadata for a list of channel IDs.

        Args:
            channel_ids: List of YouTube channel IDs (max 50 per call)

        Returns:
            List of channel metadata dictionaries containing:
                - channel_id
                - channel_title
                - description
                - subscriber_count
                - video_count
                - view_count
                - published_at

        Raises:
            ValueError: If more than 50 channel IDs provided
            HttpError: If API request fails
        """
        if len(channel_ids) > config.YOUTUBE_BATCH_SIZE:
            raise ValueError(
                f"Maximum {config.YOUTUBE_BATCH_SIZE} channel IDs per request. "
                f"Got {len(channel_ids)}"
            )

        # Check quota availability
        if not self.quota_tracker.is_available(1):
            logger.warning("Quota limit reached")
            return []

        # Filter out empty/None channel IDs
        channel_ids = [cid for cid in channel_ids if cid]

        if not channel_ids:
            return []

        try:
            # Rate limiting
            time.sleep(config.RATE_LIMIT_DELAY)

            # Call YouTube API
            logger.info(f"Fetching metadata for {len(channel_ids)} channels")
            request = self.youtube.channels().list(
                part="snippet,statistics",
                id=",".join(channel_ids)
            )
            response = request.execute()

            # Track quota usage (1 unit per call)
            self.quota_tracker.use_quota(1)

            # Parse response
            results = []
            for item in response.get("items", []):
                channel_data = self._parse_channel_item(item)
                if channel_data:
                    results.append(channel_data)

            logger.info(
                f"Successfully fetched metadata for {len(results)} channels. "
                f"Quota used: {self.quota_tracker.units_used}/"
                f"{self.quota_tracker.limit}"
            )

            return results

        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise

    def _parse_channel_item(self, item: Dict) -> Optional[Dict]:
        """
        Parse a channel item from YouTube API response.

        Args:
            item: Channel item from API response

        Returns:
            Parsed channel metadata dictionary or None if parsing fails
        """
        try:
            channel_id = item["id"]
            snippet = item["snippet"]
            statistics = item.get("statistics", {})

            return {
                "channel_id": channel_id,
                "channel_title": snippet.get("title"),
                "description": snippet.get("description"),
                "subscriber_count": int(statistics.get("subscriberCount", 0)),
                "video_count": int(statistics.get("videoCount", 0)),
                "view_count": int(statistics.get("viewCount", 0)),
                "published_at": snippet.get("publishedAt"),
                "enriched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error parsing channel item: {e}")
            return None

    def get_quota_usage(self) -> Dict[str, int]:
        """
        Get current quota usage statistics.

        Returns:
            Dictionary with quota information:
                - used: Units used
                - limit: Daily limit
                - remaining: Units remaining
        """
        return {
            "used": self.quota_tracker.units_used,
            "limit": self.quota_tracker.limit,
            "remaining": self.quota_tracker.remaining(),
        }

    def reset_quota(self):
        """
        Reset quota tracker.

        Should be called daily (automatically handled by DAG).
        """
        self.quota_tracker.reset()
        logger.info("Quota tracker reset")


# Convenience function for creating client
def create_client(api_key: Optional[str] = None) -> YouTubeAPIClient:
    """
    Create and return a YouTube API client instance.

    Args:
        api_key: Optional API key. If None, loads from config.

    Returns:
        YouTubeAPIClient instance

    Raises:
        ValueError: If no valid credentials found
    """
    return YouTubeAPIClient(api_key=api_key)
