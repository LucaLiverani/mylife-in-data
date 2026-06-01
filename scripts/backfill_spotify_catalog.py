"""One-time bulk enrichment of the Spotify catalog for an imported history.

The lazy `spotify_metadata_enricher` asset is built for the steady state: it
enriches ≤500 ids per run and discovers artists from
`bronze.spotify_plays_raw.artists_ids`. That's a poor fit right after a big
`import_spotify_extended_history` load, because:

  - tens of thousands of distinct track_ids would take ~hours to drain at
    500/run on the 10-minute sensor; and
  - the extended-history export carries no per-play artist ids (only the album
    artist *name*), so imported plays have `artists_ids = []`. Their artists are
    therefore never discovered from the plays table — only from the enriched
    tracks' `artists_ids`.

This script drains BOTH in one pass: every missing track in batches of 50
(/tracks?ids), then every artist referenced by an enriched track OR a play and
still missing from the catalog (/artists?ids). Idempotent — both catalog tables
are ReplacingMergeTree on the entity id, so re-runs and overlap with the live
enricher dedup for free.

    .venv/bin/python scripts/backfill_spotify_catalog.py

Needs SPOTIFY_CLIENT_ID/SECRET in infrastructure/.env and a valid token cache
at tokens/.spotify_cache (run ingestion/spotify/authenticate_local.py first).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

# Host-run tool: the .env's CLICKHOUSE_HOST targets the Docker network
# ("clickhouse"), unreachable from the VM host. Default to the published port on
# localhost unless CLICKHOUSE_HOST was set explicitly in the shell.
_ch_host = os.environ.get("CLICKHOUSE_HOST")
load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ["CLICKHOUSE_HOST"] = _ch_host or "localhost"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-spotify-catalog")

BATCH_SIZE = 50
# Spotify rate-limits on a rolling 30s window. We batch 50 ids/request (the max,
# so fewest requests for the data) AND sleep between batches to hold throughput
# to ~2 req/s — far under any limit. The client's retries=10 (honouring
# Retry-After) is the backstop; this throttle is so we never lean on it.
SLEEP_BETWEEN_BATCHES_S = 0.3


def _spotify_client():
    """spotipy client backed by the host token cache — mirrors SpotifyResource."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.cache_handler import CacheFileHandler

    cache_path = REPO_ROOT / "tokens" / ".spotify_cache"
    if not cache_path.exists():
        raise SystemExit(
            f"Spotify token cache not found at {cache_path}. "
            "Run .venv/bin/python ingestion/spotify/authenticate_local.py first."
        )
    auth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback"),
        scope=(
            "user-read-currently-playing user-read-playback-state "
            "user-read-recently-played user-read-private user-library-read"
        ),
        cache_handler=CacheFileHandler(cache_path=str(cache_path)),
        open_browser=False,
    )
    # retries lets spotipy ride out Spotify's 429s (honours Retry-After) over a
    # few hundred batched requests without us hand-rolling backoff.
    return spotipy.Spotify(auth_manager=auth, requests_timeout=30, retries=10)


def _missing_track_ids(client) -> list[str]:
    sql = (
        "SELECT DISTINCT track_id FROM bronze.spotify_plays_raw "
        "WHERE track_id != '' AND track_id NOT IN (SELECT track_id FROM bronze.spotify_tracks)"
    )
    return [r[0] for r in client.query(sql).result_rows]


def _missing_artist_ids(client) -> list[str]:
    # Artists referenced by an enriched track OR a play, still uncatalogued.
    # The tracks side is what surfaces imported-history artists (plays carry no
    # per-play artist ids for the extended export).
    sql = (
        "SELECT DISTINCT aid FROM ("
        "  SELECT arrayJoin(artists_ids) AS aid FROM bronze.spotify_tracks"
        "  UNION DISTINCT"
        "  SELECT arrayJoin(artists_ids) AS aid FROM bronze.spotify_plays_raw"
        ") WHERE aid != '' AND aid NOT IN (SELECT artist_id FROM bronze.spotify_artists)"
    )
    return [r[0] for r in client.query(sql).result_rows]


def main() -> int:
    from ingestion._shared.clickhouse import get_client, insert_rows
    from ingestion.spotify.enrichment import _chunked, _track_row, _artist_row

    sp = _spotify_client()
    client = get_client()

    track_ids = _missing_track_ids(client)
    log.info("Tracks to enrich: %d", len(track_ids))
    n_tracks = 0
    batches = list(_chunked(track_ids, BATCH_SIZE))
    for i, batch in enumerate(batches, 1):
        resp = sp.tracks(batch)
        rows = [_track_row(t) for t in (resp.get("tracks") or []) if t]
        if rows:
            insert_rows("spotify_tracks", rows, database="bronze")
            n_tracks += len(rows)
        if i % 20 == 0 or i == len(batches):
            log.info("  tracks: %d/%d batches, +%d rows", i, len(batches), n_tracks)
        if i < len(batches):
            time.sleep(SLEEP_BETWEEN_BATCHES_S)

    # Re-query AFTER track enrichment so the tracks' artists_ids are visible.
    artist_ids = _missing_artist_ids(client)
    log.info("Artists to enrich: %d", len(artist_ids))
    n_artists = 0
    batches = list(_chunked(artist_ids, BATCH_SIZE))
    for i, batch in enumerate(batches, 1):
        resp = sp.artists(batch)
        rows = [_artist_row(a) for a in (resp.get("artists") or []) if a]
        if rows:
            insert_rows("spotify_artists", rows, database="bronze")
            n_artists += len(rows)
        if i % 20 == 0 or i == len(batches):
            log.info("  artists: %d/%d batches, +%d rows", i, len(batches), n_artists)
        if i < len(batches):
            time.sleep(SLEEP_BETWEEN_BATCHES_S)

    log.info("Catalog backfill complete: +%d tracks, +%d artists.", n_tracks, n_artists)
    return 0


if __name__ == "__main__":
    sys.exit(main())
