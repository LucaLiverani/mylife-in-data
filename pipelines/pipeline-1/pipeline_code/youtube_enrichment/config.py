"""
Configuration for YouTube Enrichment

Manages API settings, quota limits, and other configuration parameters.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
DATA_DIR = BASE_DIR / "data"

# YouTube API Configuration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_API_CREDENTIALS_FILE = CREDENTIALS_DIR / "youtube_api_credentials.json"
YOUTUBE_API_KEY_FILE = CREDENTIALS_DIR / "youtube_api_key.txt"

# API Quota Management
YOUTUBE_API_QUOTA_LIMIT = int(os.getenv("YOUTUBE_API_QUOTA_LIMIT", "10000"))
YOUTUBE_API_DAILY_VIDEO_LIMIT = int(os.getenv("YOUTUBE_API_DAILY_VIDEO_LIMIT", "5000"))
YOUTUBE_BATCH_SIZE = int(os.getenv("YOUTUBE_BATCH_SIZE", "50"))  # Max videos per API call

# Rate Limiting
RATE_LIMIT_CALLS_PER_SECOND = 1  # Be conservative to avoid hitting rate limits
RATE_LIMIT_DELAY = 1.0  # Seconds between API calls

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds
BACKOFF_FACTOR = 2  # Exponential backoff multiplier

# ClickHouse Configuration
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse08062013")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")

# Storage Configuration
ENRICHED_DATA_OUTPUT_DIR = DATA_DIR / "enriched" / "youtube"
ENRICHED_DATA_FORMAT = "jsonl.gz"  # Format for storing enriched data

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "logs" / "youtube_enrichment.log"

# YouTube API Service Name and Version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Category mapping (YouTube category IDs to names)
# Full list: https://developers.google.com/youtube/v3/docs/videoCategories/list
YOUTUBE_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "18": "Short Movies",
    "19": "Travel & Events",
    "20": "Gaming",
    "21": "Videoblogging",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
    "30": "Movies",
    "31": "Anime/Animation",
    "32": "Action/Adventure",
    "33": "Classics",
    "34": "Documentary",
    "35": "Drama",
    "36": "Family",
    "37": "Foreign",
    "38": "Horror",
    "39": "Sci-Fi/Fantasy",
    "40": "Thriller",
    "41": "Shorts",
    "42": "Shows",
    "43": "Trailers",
}


def get_api_key() -> Optional[str]:
    """
    Get YouTube API key from environment variable or file.

    Priority:
    1. YOUTUBE_API_KEY environment variable
    2. youtube_api_key.txt file
    3. None (will raise error later)
    """
    # Try environment variable first
    if YOUTUBE_API_KEY:
        return YOUTUBE_API_KEY

    # Try reading from file
    if YOUTUBE_API_KEY_FILE.exists():
        with open(YOUTUBE_API_KEY_FILE, "r") as f:
            api_key = f.read().strip()
            if api_key:
                return api_key

    return None


def get_credentials_file() -> Optional[Path]:
    """
    Get path to YouTube API credentials JSON file.

    Returns None if file doesn't exist.
    """
    if YOUTUBE_API_CREDENTIALS_FILE.exists():
        return YOUTUBE_API_CREDENTIALS_FILE
    return None


def validate_config() -> bool:
    """
    Validate that required configuration is present.

    Returns:
        True if configuration is valid, False otherwise
    """
    errors = []

    # Check for API credentials
    api_key = get_api_key()
    credentials_file = get_credentials_file()

    if not api_key and not credentials_file:
        errors.append(
            "No YouTube API credentials found. "
            "Set YOUTUBE_API_KEY environment variable or create credentials file."
        )

    # Check ClickHouse configuration
    if not CLICKHOUSE_HOST:
        errors.append("CLICKHOUSE_HOST not configured")

    # Create necessary directories
    ENRICHED_DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if errors:
        for error in errors:
            print(f"Configuration Error: {error}")
        return False

    return True


def get_category_name(category_id: str) -> str:
    """
    Get category name from category ID.

    Args:
        category_id: YouTube category ID

    Returns:
        Category name or "Unknown" if not found
    """
    return YOUTUBE_CATEGORIES.get(str(category_id), "Unknown")


# Quota tracking
class QuotaTracker:
    """
    Simple in-memory quota tracker.

    In production, this should use a persistent store (Redis, database, etc.)
    """

    def __init__(self):
        self.units_used = 0
        self.limit = YOUTUBE_API_QUOTA_LIMIT

    def use_quota(self, units: int = 1):
        """Record quota usage"""
        self.units_used += units

    def remaining(self) -> int:
        """Get remaining quota"""
        return max(0, self.limit - self.units_used)

    def is_available(self, units: int = 1) -> bool:
        """Check if quota is available"""
        return self.remaining() >= units

    def reset(self):
        """Reset quota (should be called daily)"""
        self.units_used = 0


# Global quota tracker instance
quota_tracker = QuotaTracker()
