import sys
import os
from pathlib import Path
import json
import spotipy


try:
    project_root = Path(__file__).resolve().parents[1]
except NameError:
    project_root = Path.cwd().parent

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
    print(f"✓ Added project root to sys.path: {project_root}")


from spotify.spotify_api import get_spotify_local_client, get_recently_played_tracks, get_currently_playing, get_current_track_simplified

print("Attempting to authenticate with Spotify...")

try:
    # The get_spotify_local_client function will now print instructions.
    # If authentication is needed, it will open a browser window.
    sp = get_spotify_local_client()
    print("\n✓ Spotify client authenticated successfully.")
except spotipy.SpotifyException as e:
    print(f"\nAuthentication failed: {e}")
    print("Please check your SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and that the Redirect URI is correctly set in the Spotify Developer Dashboard.")
    sys.exit(1)
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
    sys.exit(1)


print("\n🎧 Checking currently playing track (full details)...")
current_playing = get_currently_playing(sp)

if current_playing:
    print(json.dumps(current_playing, indent=2))
else:
    print("No track is currently playing.")
    print(current_playing)

print("\n🎵 Checking currently playing track (simplified)...")
current_track = get_current_track_simplified(sp)

if current_track:
    print(json.dumps(current_track, indent=2))
else:
    print("No track is currently playing.")
    print(current_track)

artist_uri = ["spotify:artist:7ry8L53T4oJtSIogGYuioq"]

track = sp.artists(artist_uri)

print(f"== Artist Details ==")
print(json.dumps(track, indent=2))