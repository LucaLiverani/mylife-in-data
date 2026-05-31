-- Phase 2 — Spotify history (recently-played, saved tracks) + entity catalogs.
-- All ingest paths are batch INSERTs from Dagster, not Kafka — these are
-- low-volume API responses with natural dedup keys; Kafka would be overkill.

CREATE TABLE IF NOT EXISTS bronze.spotify_plays_raw (
    played_at          DateTime64(3),
    track_id           String,
    track_uri          String,
    track_name         String,
    artists_ids        Array(String),
    artists_names      Array(String),
    album_name         String,
    album_images       Array(String),
    duration_ms        Int32,
    context_type       LowCardinality(String),
    context_uri        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, played_at);

-- The /me/player/recently-played response already carries the track/album/
-- artist names and album art, so we capture them at ingest — the Recently
-- Played list then renders titles + art with zero wait for the enricher.
-- These ADDs are idempotent: no-ops on fresh tables, and patch the columns
-- onto a pre-existing spotify_plays_raw on redeploy.
ALTER TABLE bronze.spotify_plays_raw ADD COLUMN IF NOT EXISTS track_name    String        AFTER track_uri;
ALTER TABLE bronze.spotify_plays_raw ADD COLUMN IF NOT EXISTS artists_names Array(String) AFTER artists_ids;
ALTER TABLE bronze.spotify_plays_raw ADD COLUMN IF NOT EXISTS album_name    String        AFTER artists_names;
ALTER TABLE bronze.spotify_plays_raw ADD COLUMN IF NOT EXISTS album_images  Array(String) AFTER album_name;

CREATE TABLE IF NOT EXISTS bronze.spotify_tracks (
    track_id           String,
    track_name         String,
    track_uri          String,
    duration_ms        Int32,
    explicit           Bool,
    popularity         Int32,
    isrc               String,
    album_id           String,
    album_name         String,
    album_uri          String,
    album_images       Array(String),
    album_release_date Nullable(Date),
    artists_ids        Array(String),
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY track_id;

CREATE TABLE IF NOT EXISTS bronze.spotify_artists (
    artist_id          String,
    artist_name        String,
    artist_uri         String,
    genres             Array(LowCardinality(String)),
    popularity         Int32,
    followers          Int32,
    image_url          String,
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY artist_id;

CREATE TABLE IF NOT EXISTS bronze.spotify_saved_tracks (
    added_at           DateTime64(3),
    track_id           String,
    track_uri          String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, added_at);
