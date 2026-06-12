"""Long-running producer for /me/player/currently-playing.

Loop:
  - poll Spotify every POLL_INTERVAL_SECONDS
  - on track change or is_playing flip, validate the event against the topic's
    JSON Schema contract and publish it to `spotify.player.current`
  - events that violate the contract are wrapped in an envelope and routed to
    `spotify.player.current.dlq` (→ bronze.spotify_player_current_dlq) instead
    of being silently dropped by the ClickHouse Kafka engine
  - back off on HTTP 429 (Retry-After), retry once on 401 with token refresh

The contract (schemas/spotify_player_current.v1.json) is also registered in
the Redpanda Schema Registry at startup, best-effort: the registry stores and
compatibility-checks the contract, but enforcement is local — the ClickHouse
consumer reads plain JSONEachRow, so the registry wire format can't be used.

Run as a Docker service (spotify-current-producer) — `command: python
ingestion/spotify/producer_current.py`.

Environment:
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
  KAFKA_BOOTSTRAP_SERVERS (defaults to redpanda:9092)
  SCHEMA_REGISTRY_URL (defaults to http://redpanda:8081)
  Token cache at /opt/dagster/tokens/.spotify_cache (bind-mounted in)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import spotipy
from prometheus_client import Counter, Gauge, start_http_server
from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

# Allow imports like `ingestion._shared.redpanda` whether we're running
# in the dagster image (PYTHONPATH=/opt/dagster/repo) or directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion._shared.json_utils import dumps  # noqa: E402
from ingestion._shared.redpanda import ensure_topic, get_producer  # noqa: E402
from ingestion._shared.schema_registry import ensure_registered  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("spotify-current-producer")

TOPIC = "spotify.player.current"
DLQ_TOPIC = f"{TOPIC}.dlq"
DLQ_RETENTION_MS = 7 * 24 * 3600 * 1000
SCHEMA_SUBJECT = f"{TOPIC}-value"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "spotify_player_current.v1.json"
SCOPES = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-read-recently-played "
    "user-read-private "
    "user-library-read"
)
DEFAULT_CACHE_PATH = "/opt/dagster/tokens/.spotify_cache"
POLL_INTERVAL_SECONDS = 5
METRICS_PORT = int(os.environ.get("PRODUCER_METRICS_PORT", "9110"))

# Heartbeat for the monitoring stack (this container is not a Dagster run, so
# run_failure_alert_sensor can't see it — Prometheus scrapes these instead;
# alert rules live in infrastructure/compose/monitoring/alerts/).
POLLS = Counter(
    "spotify_producer_polls_total", "Successful Spotify API poll cycles"
)
POLL_ERRORS = Counter(
    "spotify_producer_poll_errors_total", "Failed Spotify API poll cycles", ["kind"]
)
EVENTS_PUBLISHED = Counter(
    "spotify_producer_events_published_total",
    "State-transition events published to Redpanda",
    ["outcome"],  # ok → spotify.player.current, dlq → its dead-letter sibling
)
PUBLISH_FAILURES = Counter(
    "spotify_producer_kafka_publish_failures_total",
    "Events that failed to publish to Redpanda entirely",
)
LAST_OK_POLL = Gauge(
    "spotify_producer_last_successful_poll_timestamp_seconds",
    "Unix time of the last successful Spotify API poll",
)
# Pre-seed every label combination so increase()/rate() see 0 instead of an
# absent series before the first occurrence.
for _kind in ("rate_limited", "auth", "spotify_error", "unexpected"):
    POLL_ERRORS.labels(kind=_kind)
for _outcome in ("ok", "dlq"):
    EVENTS_PUBLISHED.labels(outcome=_outcome)

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


def load_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    return schema


def serialize_event(
    validator: jsonschema.Draft7Validator, event: dict[str, Any]
) -> tuple[str, list[str]]:
    """Serialize the event to its wire form and validate that exact form.

    dumps() is what the producer's value_serializer applies (datetime → the
    ClickHouse-basic string form), so round-tripping through it is the honest
    contract check — validating the in-memory dict would miss serializer
    regressions like the ISO-'T'/'Z' one that once emptied the table.

    Returns (payload, errors). Never raises: an event that won't even
    serialize comes back as (repr(event), [the TypeError]) so it still routes
    to the DLQ instead of crash-looping the producer."""
    try:
        payload = dumps(event)
    except (TypeError, ValueError) as exc:
        return repr(event), [f"<root>: event is not JSON-serializable: {exc}"]
    errors = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(json.loads(payload)), key=str)
    ]
    return payload, errors


def dlq_envelope(payload: str, errors: list[str]) -> dict[str, Any]:
    """Wrap a rejected event for the dead-letter topic. Keys mirror the
    columns of bronze.kafka_spotify_player_current_dlq."""
    return {
        "rejected_at": datetime.now(tz=timezone.utc),
        "topic": TOPIC,
        "error": "; ".join(errors),
        "payload": payload,
    }


def main() -> int:
    cache_path = os.environ.get("SPOTIFY_CACHE_PATH", DEFAULT_CACHE_PATH)
    if not Path(cache_path).exists():
        log.error("Spotify token cache not found at %s — run authenticate_local.py", cache_path)
        return 1

    schema = load_schema()
    validator = jsonschema.Draft7Validator(schema)
    ensure_registered(SCHEMA_SUBJECT, schema)  # best-effort; see schema_registry.py
    try:
        ensure_topic(DLQ_TOPIC, retention_ms=DLQ_RETENTION_MS)
    except Exception:
        log.exception("Could not ensure DLQ topic %s exists", DLQ_TOPIC)

    sp = _build_spotify_client(cache_path)
    producer = get_producer()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    start_http_server(METRICS_PORT)
    LAST_OK_POLL.set_to_current_time()  # grace until the first real poll lands
    log.info("Metrics on :%s/metrics", METRICS_PORT)
    log.info("Producer started — polling %s every %ss → topic %s", "currently-playing", POLL_INTERVAL_SECONDS, TOPIC)
    prev: dict[str, Any] | None = None

    while _running:
        try:
            payload = sp.current_playback()
            if not payload or not payload.get("item"):
                # /me/player reports nothing when Spotify has no "active device",
                # even while a track is playing. /me/player/currently-playing is
                # more lenient — fall back to it (device fields stay empty).
                payload = sp.current_user_playing_track()
            event = _normalize_event(payload) if payload else None
        except SpotifyException as exc:
            if exc.http_status == 429:
                POLL_ERRORS.labels(kind="rate_limited").inc()
                retry_after = int(exc.headers.get("Retry-After", "10")) if exc.headers else 10
                log.warning("429 — backing off %ss", retry_after)
                time.sleep(retry_after)
                continue
            if exc.http_status == 401:
                POLL_ERRORS.labels(kind="auth").inc()
                log.info("401 — refreshing token")
                # spotipy refreshes on next call when token expired; just retry.
                time.sleep(2)
                continue
            POLL_ERRORS.labels(kind="spotify_error").inc()
            log.exception("Spotify error: %s", exc)
            time.sleep(POLL_INTERVAL_SECONDS * 2)
            continue
        except Exception:
            POLL_ERRORS.labels(kind="unexpected").inc()
            log.exception("Unexpected error polling Spotify")
            time.sleep(POLL_INTERVAL_SECONDS * 2)
            continue

        POLLS.inc()
        LAST_OK_POLL.set_to_current_time()

        if event is not None and _events_differ(prev, event):
            wire, errors = serialize_event(validator, event)
            try:
                if errors:
                    log.error(
                        "Contract violation — routing to %s (track_id=%s): %s",
                        DLQ_TOPIC, event.get("track_id"), "; ".join(errors),
                    )
                    producer.send(DLQ_TOPIC, value=dlq_envelope(wire, errors))
                else:
                    producer.send(TOPIC, value=event, key=event.get("track_id") or None)
                producer.flush(timeout=5)
                EVENTS_PUBLISHED.labels(outcome="dlq" if errors else "ok").inc()
                if not errors:
                    log.info(
                        "→ %s — %s (playing=%s)",
                        event.get("track_name"),
                        ", ".join(event.get("artists_names") or []),
                        event.get("is_playing"),
                    )
                # Either way this transition is handled — advancing prev keeps
                # a bad state from re-rejecting on every poll.
                prev = event
            except Exception:
                PUBLISH_FAILURES.inc()
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
