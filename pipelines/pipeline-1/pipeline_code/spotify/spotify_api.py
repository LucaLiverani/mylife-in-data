import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from spotify.airflow_cache_handler import AirflowCacheHandler

load_dotenv()

def get_spotify_client():
    """Initializes and returns a Spotify client."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    scopes = "user-read-recently-played"

    cache_handler = AirflowCacheHandler()

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_handler=cache_handler,
    )

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
        print(f"Error fetching recently played tracks: {e}")
        raise
