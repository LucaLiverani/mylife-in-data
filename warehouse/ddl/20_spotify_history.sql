-- Phase 2 — Spotify history (recently-played, saved tracks) + entity catalogs.
-- All ingest paths are batch INSERTs from Dagster, not Kafka — these are
-- low-volume API responses with natural dedup keys; Kafka would be overkill.

CREATE TABLE IF NOT EXISTS bronze.spotify_plays_raw (
    played_at          DateTime64(3),
    track_id           String,
    track_uri          String,
    artists_ids        Array(String),
    duration_ms        Int32,
    context_type       LowCardinality(String),
    context_uri        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, played_at);

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
