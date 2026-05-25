"""
One-time authentication script to create Spotify token cache.

Usage (from repo root, with the host venv built):
    .venv/bin/python ingestion/spotify/authenticate_local.py

Flow (works on any host — laptop, headless VM via SSH, doesn't matter):
  1. Script prints a Spotify authorization URL.
  2. You open it in any browser (your local laptop is fine), sign in, click Accept.
  3. Spotify redirects to `http://127.0.0.1:8000/callback?code=...` — that page
     fails to load ("This site can't be reached") because nothing is listening
     there. That's expected.
  4. Copy the entire failed URL from the browser's address bar.
  5. Paste it into this script's prompt and press Enter.
  6. Script exchanges the code for tokens, writes `<repo_root>/tokens/.spotify_cache`,
     exits.

Run once per environment (laptop + VM). Caches are per-host — DO NOT scp the
cache file; spotipy rewrites it on every 401 inside the running producer
container, so copying mid-flight corrupts it. Spotify issues independent
refresh tokens per OAuth grant, so two grants is fine.
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
    
    # Create auth manager.
    # open_browser=False forces spotipy's paste-the-URL-into-stdin flow instead
    # of spinning up a local HTTP server on the redirect_uri port. The local
    # server flow breaks when the script runs on a headless host (VM via SSH)
    # because the browser is on a different machine — it would hit the
    # laptop's localhost, never reaching the VM's server. The paste flow works
    # regardless of where the script runs.
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
        show_dialog=True,        # always show consent (vs silently re-using a session)
        open_browser=False,      # paste-the-URL flow; portable across hosts
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