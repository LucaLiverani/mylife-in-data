"""Check whether this Spotify app can call the audio-features endpoint.

Audio Features (+ Audio Analysis, Related Artists, Recommendations) were
restricted by Spotify on 2024-11-27 — any app not on Extended Quota at that
date lost access, and new apps registered after never had it. The only
definitive check is to actually call the endpoint.

Usage (from repo root):
    python3 scripts/check_audio_features.py

Exit codes:
    0 = audio-features works
    1 = a prerequisite is missing (credentials, token cache, deps)
    2 = the API call was made and returned 403/blocked
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / "infrastructure" / ".env"
CACHE_PATH = REPO_ROOT / "tokens" / ".spotify_cache"
KNOWN_TRACK_ID = "4iV5W9uYEdYUVa79Axb7Rh"  # Radiohead — Paranoid Android, stable since forever


def fail(msg: str, code: int = 1) -> None:
    print(f"\n{msg}\n", file=sys.stderr)
    sys.exit(code)


try:
    from dotenv import load_dotenv
except ImportError:
    fail("Missing python-dotenv. Install: pip install python-dotenv")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.cache_handler import CacheFileHandler
except ImportError:
    fail(
        "Missing spotipy. Install in a venv:\n"
        "    python3 -m venv .venv && source .venv/bin/activate\n"
        "    pip install spotipy python-dotenv"
    )

if not ENV_PATH.exists():
    fail(f"No env file at {ENV_PATH}. Copy infrastructure/.env.example and fill in SPOTIFY_*.")
load_dotenv(ENV_PATH)

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

missing = [n for n, v in [("SPOTIFY_CLIENT_ID", client_id), ("SPOTIFY_CLIENT_SECRET", client_secret)] if not v]
if missing:
    fail(
        f"Missing {' and '.join(missing)} in {ENV_PATH}.\n"
        "1. Register an app at https://developer.spotify.com/dashboard\n"
        "2. Add a redirect URI matching SPOTIFY_REDIRECT_URI (default http://localhost:8888/callback)\n"
        f"3. Append SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI to {ENV_PATH}"
    )

if not CACHE_PATH.exists():
    fail(
        f"No token cache at {CACHE_PATH}.\n"
        "Run the one-time auth flow first:\n"
        "    python3 ingestion/spotify/authenticate_local.py"
    )

auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope="user-read-currently-playing",
    cache_handler=CacheFileHandler(cache_path=str(CACHE_PATH)),
    open_browser=False,
)
sp = spotipy.Spotify(auth_manager=auth_manager)

print(f"Calling GET /audio-features/{KNOWN_TRACK_ID} ...")
try:
    features = sp.audio_features([KNOWN_TRACK_ID])
except spotipy.SpotifyException as e:
    if e.http_status == 403:
        print(f"BLOCKED (403): {e.msg}")
        print("→ This app is on the post-2024-11-27 side of the deprecation. Drop audio-features tiles from scope.")
        sys.exit(2)
    raise

if not features or features[0] is None:
    print("Empty response (no error, but no payload). Treat as blocked.")
    sys.exit(2)

f = features[0]
print("OK — audio-features works for this app.")
print(f"  danceability={f['danceability']}  energy={f['energy']}  valence={f['valence']}  tempo={f['tempo']}")
