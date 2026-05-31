"""Import a Spotify "Extended streaming history" GDPR export.

This is the ONLY source of full Spotify listening history: the
`/me/player/recently-played` API returns just the last 50 plays, so the live
`spotify_recently_played` asset can never reach further back. Request the export
from Spotify -> Account -> Privacy settings -> "Download your data" -> check
"Extended streaming history". It arrives within ~30 days as a ZIP of
`Streaming_History_Audio_*.json` files (one object per play).

Idempotent: bronze.spotify_plays_raw is ReplacingMergeTree on
(track_id, played_at), so re-imports — and overlap with the live capture —
dedup automatically. Podcast/episode entries (no track URI) are skipped.
Per-track artist ids, album art and duration aren't in the export; the
`spotify_metadata_enricher` asset backfills the catalog tables off track_id.

The source can be a local path or an R2 location (needs R2_* in
infrastructure/.env):
    .venv/bin/python scripts/import_spotify_extended_history.py /path/to/my_spotify_data.zip
    .venv/bin/python scripts/import_spotify_extended_history.py r2://spotify/my_spotify_data.zip
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "infrastructure" / ".env")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("import-spotify-history")


def _track_id_from_uri(uri: str) -> str:
    # "spotify:track:6rqhFgbbKwnb9MLmUQDhG6" -> "6rqhFgbbKwnb9MLmUQDhG6".
    # Episodes carry spotify_episode_uri instead, so their track uri is null.
    parts = (uri or "").split(":")
    return parts[2] if len(parts) == 3 and parts[1] == "track" else ""


def _row(entry: dict) -> dict | None:
    track_uri = entry.get("spotify_track_uri") or ""
    track_id = _track_id_from_uri(track_uri)
    ts = entry.get("ts")
    if not track_id or not ts:
        return None  # podcast episode / malformed — skip
    artist = entry.get("master_metadata_album_artist_name") or ""
    # Mirror ingestion/spotify/recently_played.py:_row_from_play exactly so live
    # + historical rows are column-aligned. Fields the export lacks stay empty;
    # the enricher fills the catalog. Spotify stamps ts as ISO-8601 with 'Z'.
    return {
        "played_at": datetime.fromisoformat(ts.replace("Z", "+00:00")),
        "track_id": track_id,
        "track_uri": track_uri,
        "track_name": entry.get("master_metadata_track_name") or "",
        "artists_ids": [],
        "artists_names": [artist] if artist else [],
        "album_name": entry.get("master_metadata_album_album_name") or "",
        "album_images": [],
        "duration_ms": 0,
        "context_type": "",
        "context_uri": "",
    }


def _history_files(root: Path) -> list[Path]:
    # `Streaming_History_Audio_*` is the extended export; `endsong_*` is the
    # name older exports used. (Streaming_History_Video_* is podcast video —
    # no music plays, skipped.)
    files = sorted(root.rglob("Streaming_History_Audio_*.json"))
    files += sorted(root.rglob("endsong_*.json"))
    return files


def main() -> int:
    from ingestion._shared.clickhouse import insert_rows
    from ingestion._shared.import_source import open_archive_root

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source",
        help="Local path (zip or dir) or R2 location (r2://<key> or r2://<prefix>/).",
    )
    args = parser.parse_args()

    rows: list[dict] = []
    skipped = 0
    try:
        with open_archive_root(args.source) as root:
            files = _history_files(root)
            if not files:
                log.error(
                    "No Streaming_History_Audio_*.json (or endsong_*.json) in the source — make "
                    "sure you requested *Extended* streaming history, not just Account data."
                )
                return 2
            for f in files:
                try:
                    entries = json.loads(f.read_text(encoding="utf-8"))
                except Exception as exc:
                    log.warning("Could not parse %s: %s", f.name, exc)
                    continue
                kept = 0
                for entry in entries:
                    row = _row(entry)
                    if row is None:
                        skipped += 1
                    else:
                        rows.append(row)
                        kept += 1
                log.info("  %s -> %d plays (%d entries)", f.name, kept, len(entries))
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1

    if not rows:
        log.error("Parsed 0 music plays (%d non-track entries skipped).", skipped)
        return 2

    insert_rows("spotify_plays_raw", rows, database="bronze")
    log.info(
        "Inserted %d plays into bronze.spotify_plays_raw (%d non-track entries skipped).",
        len(rows), skipped,
    )
    log.info("Run `spotify_metadata_enricher` in Dagster to backfill track/artist/album metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
