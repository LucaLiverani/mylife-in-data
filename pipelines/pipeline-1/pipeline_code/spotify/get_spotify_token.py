import os
import sys
import json
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Add the parent directory to the path to find the spotify module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from spotify.spotify_api import get_spotify_client

def get_token():
    """
    Runs the Spotify authentication flow and prints the token cache.
    """
    print("Attempting to get Spotify token...")
    # This will trigger the browser-based authentication
    get_spotify_client()

    cache_path = ".spotipy_token_cache"
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            print("\nAuthentication successful!")
            print("Copy the following JSON and save it as an Airflow Variable with the key 'SPOTIFY_TOKEN_CACHE':\n")
            # Pretty print the JSON
            token_info = json.load(f)
            print(json.dumps(token_info, indent=4))
    else:
        print("\nCould not find token cache file. Authentication may have failed.")

if __name__ == "__main__":
    # Load environment variables from .env file in the parent directory
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    get_token()
