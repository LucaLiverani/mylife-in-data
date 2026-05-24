"""
One-time authentication script to create Spotify token cache.
This MUST be run on your host machine (not in Docker).

Usage (from repo root, with venv active):
    .venv/bin/python ingestion/spotify/authenticate_local.py

This will:
1. Open browser for Spotify authentication
2. Create token cache file at <repo_root>/tokens/.spotify_cache
3. The tokens/ directory is bind-mounted into the Dagster container.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def authenticate():
    """Perform interactive Spotify authentication"""

    load_dotenv(REPO_ROOT / "infrastructure" / ".env")

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    scopes = (
        "user-read-recently-played user-read-playback-state "
        "user-read-currently-playing user-read-private user-library-read"
    )

    tokens_dir = REPO_ROOT / "tokens"
    tokens_dir.mkdir(exist_ok=True)

    cache_path = tokens_dir / ".spotify_cache"
    
    log.info("="*60)
    log.info("Spotify Authentication for Standalone Producer")
    log.info("="*60)
    log.info(f"Client ID: {client_id[:8]}...")
    log.info(f"Redirect URI: {redirect_uri}")
    log.info(f"Token cache: {cache_path}")
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
        show_dialog=True,  # Always show auth dialog
    )
    
    # This will trigger browser authentication if needed
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    # Test the connection
    try:
        user = sp.current_user()
        if user:
            log.info(f"\nAuthentication successful!")
            log.info(f"Logged in as: {user['display_name']} ({user['id']})")
            log.info(f"\nToken cache created at: {cache_path}")
            log.info("\nYou can now run the standalone producer:")
            log.info("  docker-compose up -d spotify-current-producer")
            log.info("\nOr locally:")
            log.info("  python producers/spotify_current_playing_producer.py")
        else:
            log.error("\nAuthentication succeeded, but failed to fetch user details.")
            log.error("Please check your client ID, secret, and scopes.")
            sys.exit(1)
        
    except Exception as e:
        log.error(f"\nAuthentication failed: {e}")
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