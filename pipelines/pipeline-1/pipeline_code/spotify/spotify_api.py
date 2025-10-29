import os
import spotipy
import logging
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

def get_spotify_client():
    """Initializes and returns a Spotify client for Airflow."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080")
    scopes = "user-read-recently-played user-read-playback-state user-read-currently-playing"
    
    # Import here to avoid circular dependency
    from spotify.airflow_cache_handler import AirflowCacheHandler
    cache_handler = AirflowCacheHandler()
    
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
    )
    
    return spotipy.Spotify(auth_manager=auth_manager)

def get_spotify_local_client():
    """
    Initializes and returns a Spotify client for local development.
    Handles the interactive authentication flow.
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    scopes = "user-read-recently-played user-read-playback-state user-read-currently-playing"
    
    log.info("--- Spotify Local Authentication ---")
    log.info(f"CLIENT_ID: {client_id[:4]}... (loaded from .env)")
    log.info(f"REDIRECT_URI: {redirect_uri}")
    
    # Use a file-based cache for local development
    cache_handler = CacheFileHandler(cache_path='./.spotipy_token_cache')
    
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
        show_dialog=True,
    )
    
    return spotipy.Spotify(auth_manager=auth_manager)

def get_spotify_producer_client():
    """
    Spotify client for standalone producer (Docker container).
    
    IMPORTANT: Must authenticate locally FIRST to create token file.
    Run: python scripts/authenticate_spotify.py
    
    This function:
    - Uses file-based cache (persisted via Docker volume)
    - Automatically refreshes expired tokens
    - Does NOT require interactive authentication
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    scopes = "user-read-recently-played user-read-playback-state user-read-currently-playing"
    
    # Token cache path (will be mounted as Docker volume)
    cache_path = os.getenv("SPOTIFY_TOKEN_CACHE_PATH", "/app/tokens/.spotify_cache")
    
    log.info(f"Using Spotify token cache: {cache_path}")
    
    # Check if token file exists
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"Spotify token cache not found at {cache_path}. "
            "Please run 'python scripts/authenticate_spotify.py' first to create it."
        )
    
    cache_handler = CacheFileHandler(cache_path=cache_path)
    
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
        show_dialog=False,  # No interactive auth
    )
    
    # Verify token is valid
    token_info = auth_manager.get_cached_token()
    if not token_info:
        raise ValueError(
            "No valid Spotify token found. "
            "Please run 'python scripts/authenticate_spotify.py' first."
        )
    
    log.info("Spotify client authenticated successfully")
    return spotipy.Spotify(auth_manager=auth_manager)

def get_recently_played_tracks(sp, after=None):
    """
    Fetches recently played tracks from the Spotify API after a given timestamp.
    """
    try:
        if after:
            recent_tracks = sp.current_user_recently_played(limit=50, after=after)
        else:
            recent_tracks = sp.current_user_recently_played(limit=50)
        return recent_tracks
    except Exception as e:
        log.error(f"Error fetching recently played tracks: {e}")
        raise

def get_currently_playing(sp):
    """
    Get currently playing track (for real-time streaming).
    Used by standalone producer.
    
    Returns:
        dict: Current playback info or None if nothing playing
    """
    try:
        current = sp.current_playback()
        
        if current is None or not current.get('is_playing'):
            return None
        
        return current
    
    except Exception as e:
        log.error(f"Error fetching currently playing: {e}")
        raise

def get_current_track_simplified(sp):
    """
    Get simplified currently playing track info.
    Lighter weight than full playback state.
    """
    try:
        current = sp.currently_playing()
        
        if current is None or not current.get('is_playing'):
            return None
        
        return current
    
    except Exception as e:
        log.error(f"Error fetching current track: {e}")
        raise

def get_artists(sp, artists=[]):    
    """
    Get artist details.
    """
    try:
        artists = sp.artists(artists)
        return artists
    except Exception as e:
        log.error(f"Error fetching artist details: {e}")
        raise
        