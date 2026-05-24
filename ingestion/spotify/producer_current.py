"""Long-running producer for /me/player/currently-playing.

Loop:
  - poll Spotify every POLL_INTERVAL_SECONDS
  - on track change or is_playing flip, publish one JSON message to topic
    `spotify.player.current`
  - back off on HTTP 429 (Retry-After), retry once on 401 with token refresh

Run as a Docker service (spotify-current-producer) — `command: python
ingestion/spotify/producer_current.py`.

Environment:
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
  KAFKA_BOOTSTRAP_SERVERS (defaults to redpanda:9092)
  Token cache at /opt/dagster/tokens/.spotify_cache (bind-mounted in)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

# Allow imports like `ingestion._shared.redpanda` whether we're running
# in the dagster image (PYTHONPATH=/opt/dagster/repo) or directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion._shared.redpanda import get_producer  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("spotify-current-producer")

TOPIC = "spotify.player.current"
SCOPES = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-read-recently-played "
    "user-read-private "
    "user-library-read"
)
DEFAULT_CACHE_PATH = "/opt/dagster/tokens/.spotify_cache"
POLL_INTERVAL_SECONDS = 5

_running = True


def _handle_signal(signum, _frame):
    global _running
    log.info("Received signal %s — shutting down…", signum)
    _running = False


def _build_spotify_client(cache_path: str) -> spotipy.Spotify:
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_handler=CacheFileHandler(cache_path=cache_path),
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _normalize_event(track: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a /me/player/currently-playing response → flat JSON row.

    Returns None when nothing is playing (no item in payload)."""

    item = track.get("item") if track else None
    if not item:
        return None

    artists = item.get("artists") or []
    album = item.get("album") or {}
    device = (track or {}).get("device") or {}
    context = (track or {}).get("context") or {}

    captured_at = datetime.now(tz=timezone.utc)

    return {
        "captured_at": captured_at,
        "track_id": item.get("id") or "",
        "track_name": item.get("name") or "",
        "track_uri": item.get("uri") or "",
        "track_duration_ms": int(item.get("duration_ms") or 0),
        "progress_ms": int(track.get("progress_ms") or 0),
        "is_playing": bool(track.get("is_playing")),
        "album_id": album.get("id") or "",
        "album_name": album.get("name") or "",
        "album_uri": album.get("uri") or "",
        "album_images": [img.get("url", "") for img in (album.get("images") or [])],
        "artists_ids": [a.get("id", "") for a in artists],
        "artists_names": [a.get("name", "") for a in artists],
        "device_id": device.get("id") or "",
        "device_name": device.get("name") or "",
        "device_type": device.get("type") or "",
        "device_volume_percent": int(device.get("volume_percent") or 0),
        "context_type": context.get("type") or "",
        "context_uri": context.get("uri") or "",
    }


def _events_differ(prev: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    """Emit only on real state transitions: track change OR is_playing flip."""
    if prev is None:
        return True
    if prev.get("track_id") != new.get("track_id"):
        return True
    if prev.get("is_playing") != new.get("is_playing"):
        return True
    return False


def main() -> int:
    cache_path = os.environ.get("SPOTIFY_CACHE_PATH", DEFAULT_CACHE_PATH)
    if not Path(cache_path).exists():
        log.error("Spotify token cache not found at %s — run authenticate_local.py", cache_path)
        return 1

    sp = _build_spotify_client(cache_path)
    producer = get_producer()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info("Producer started — polling %s every %ss → topic %s", "currently-playing", POLL_INTERVAL_SECONDS, TOPIC)
    prev: dict[str, Any] | None = None

    while _running:
        try:
            payload = sp.current_playback()
            event = _normalize_event(payload) if payload else None
        except SpotifyException as exc:
            if exc.http_status == 429:
                retry_after = int(exc.headers.get("Retry-After", "10")) if exc.headers else 10
                log.warning("429 — backing off %ss", retry_after)
                time.sleep(retry_after)
                continue
            if exc.http_status == 401:
                log.info("401 — refreshing token")
                # spotipy refreshes on next call when token expired; just retry.
                time.sleep(2)
                continue
            log.exception("Spotify error: %s", exc)
            time.sleep(POLL_INTERVAL_SECONDS * 2)
            continue
        except Exception:
            log.exception("Unexpected error polling Spotify")
            time.sleep(POLL_INTERVAL_SECONDS * 2)
            continue

        if event is not None and _events_differ(prev, event):
            try:
                producer.send(TOPIC, value=event, key=event.get("track_id") or None)
                producer.flush(timeout=5)
                log.info(
                    "→ %s — %s (playing=%s)",
                    event.get("track_name"),
                    ", ".join(event.get("artists_names") or []),
                    event.get("is_playing"),
                )
                prev = event
            except Exception:
                log.exception("Kafka publish failed")
        time.sleep(POLL_INTERVAL_SECONDS)

    log.info("Flushing producer and exiting…")
    try:
        producer.flush(timeout=5)
        producer.close(timeout=5)
    except Exception:
        log.exception("Error during producer shutdown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
