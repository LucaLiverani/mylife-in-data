import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd

load_dotenv()

def get_spotify_client():
    """Initializes and returns a Spotify client."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    scopes = "user-read-recently-played"
    cache_path = ".spotipy_token_cache"

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scopes,
        cache_path=cache_path,
        show_dialog=False,
    )

    return spotipy.Spotify(auth_manager=auth_manager)

def get_recently_played_tracks(sp):
    """
    Fetches the last 50 recently played tracks from the Spotify API.
    """
    try:
        recent_tracks = sp.current_user_recently_played(limit=50)
        return recent_tracks.get("items", [])
    except Exception as e:
        print(f"Error fetching recently played tracks: {e}")
        return []

def process_tracks(tracks):
    """
    Processes the raw track data into a structured format.
    """
    processed_data = []
    for item in tracks:
        track = item['track']
        played_at = item['played_at']
        
        processed_data.append({
            'played_at': played_at,
            'track_name': track['name'],
            'artists': ", ".join(a["name"] for a in track["artists"]),
            'album_name': track['album']['name'],
            'track_id': track['id'],
            'album_id': track['album']['id'],
            'duration_ms': track['duration_ms'],
            'popularity': track['popularity']
        })
    return processed_data

def create_dataframe(data):
    """
    Creates a pandas DataFrame from the processed track data.
    """
    df = pd.DataFrame(data)
    df['played_at'] = pd.to_datetime(df['played_at'])
    return df

def fetch_spotify_history():
    """
    Main function to fetch and process Spotify listening history.
    """
    sp = get_spotify_client()
    tracks = get_recently_played_tracks(sp)
    if tracks:
        processed_tracks = process_tracks(tracks)
        df = create_dataframe(processed_tracks)
        return df
    return pd.DataFrame()

if __name__ == "__main__":
    history_df = fetch_spotify_history()
    if not history_df.empty:
        print(f"Successfully fetched {len(history_df)} tracks.")
        print(history_df.head())
    else:
        print("No tracks fetched.")