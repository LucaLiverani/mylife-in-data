"""
One-time authentication script to create Spotify token for Airflow.
This MUST be run on your host machine (not in Docker).

Usage:
    python scripts/authenticate_spotify_for_airflow.py

This will:
1. Open browser for Spotify authentication
2. Generate token JSON
3. Show you how to add it to Airflow
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def authenticate():
    """Perform interactive Spotify authentication and generate token JSON for Airflow"""

    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    scopes = "user-read-recently-played user-read-playback-state user-read-currently-playing"

    # Create temporary cache file
    cache_path = Path("./.spotify_airflow_temp_cache")

    log.info("="*60)
    log.info("Spotify Authentication for Airflow")
    log.info("="*60)
    log.info(f"Client ID: {client_id[:8]}...")
    log.info(f"Redirect URI: {redirect_uri}")
    log.info("="*60)

    # Create cache handler
    cache_handler = CacheFileHandler(cache_path=str(cache_path))

    # Create auth manager
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
        show_dialog=True,
    )

    # This will trigger browser authentication
    sp = spotipy.Spotify(auth_manager=auth_manager)

    # Test the connection
    try:
        user = sp.current_user()
        if user:
            log.info(f"\nAuthentication successful!")
            log.info(f"Logged in as: {user['display_name']} ({user['id']})")

            # Read the token from the cache file
            with open(cache_path, 'r') as f:
                token_info = json.load(f)

            # Pretty print the token
            token_json = json.dumps(token_info, indent=2)

            log.info("\n" + "="*60)
            log.info("SPOTIFY TOKEN FOR AIRFLOW")
            log.info("="*60)
            print(token_json)
            log.info("="*60)

            log.info("\nNow add this token to Airflow:")
            log.info("\nOption 1: Using Airflow UI")
            log.info("  1. Go to http://localhost:8080")
            log.info("  2. Navigate to Admin > Variables")
            log.info("  3. Click the '+' button to add a new variable")
            log.info("  4. Key: SPOTIFY_TOKEN_CACHE")
            log.info("  5. Value: Paste the JSON above")
            log.info("  6. Click Save")

            log.info("\nOption 2: Using Airflow CLI")
            log.info("  Run this command:")
            log.info(f"  docker exec airflow-standalone airflow variables set SPOTIFY_TOKEN_CACHE '{token_json}'")

            # Clean up temp file
            cache_path.unlink()

        else:
            log.error("\nAuthentication succeeded, but failed to fetch user details.")
            sys.exit(1)

    except Exception as e:
        log.error(f"\nAuthentication failed: {e}")
        # Clean up temp file if it exists
        if cache_path.exists():
            cache_path.unlink()
        sys.exit(1)

if __name__ == '__main__':
    try:
        authenticate()
    except KeyboardInterrupt:
        log.info("\nAuthentication cancelled")
        sys.exit(1)
    except Exception as e:
        log.error(f"\nError: {e}")
        sys.exit(1)
