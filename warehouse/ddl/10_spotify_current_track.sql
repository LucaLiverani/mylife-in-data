-- Phase 1 — Spotify currently-playing pipeline.
--
-- Stream path:
--   spotify-current-producer (Python, validates each event against the JSON
--   Schema contract in ingestion/spotify/schemas/ before producing)
--     → Kafka topic `spotify.player.current` (Redpanda)
--       → bronze.kafka_spotify_player_current (Kafka engine)
--         → bronze.mv_spotify_player_current (MV)
--           → bronze.spotify_player_current (ReplacingMergeTree)
--             → gold.gold_spotify_current_track (view, dashboard hits this)
--
-- Dead-letter path (contract violations, never silently dropped):
--   producer reject envelope
--     → Kafka topic `spotify.player.current.dlq`
--       → bronze.kafka_spotify_player_current_dlq (Kafka engine)
--         → bronze.mv_spotify_player_current_dlq (MV)
--           → bronze.spotify_player_current_dlq (ReplacingMergeTree)
--
-- Schemas mirror DATA_MODEL.md — keep in sync. The Kafka-engine column set
-- must also match the JSON Schema contract; CI enforces that parity via
-- scripts/check_stream_contract.py.

-- Storage table.
CREATE TABLE IF NOT EXISTS bronze.spotify_player_current (
    captured_at             DateTime64(3),
    track_id                String,
    track_name              String,
    track_uri               String,
    track_duration_ms       Int32,
    progress_ms             Int32,
    is_playing              Bool,
    album_id                String,
    album_name              String,
    album_uri               String,
    album_images            Array(String),
    artists_ids             Array(String),
    artists_names           Array(String),
    device_id               String,
    device_name             String,
    device_type             LowCardinality(String),
    device_volume_percent   Int32,
    context_type            LowCardinality(String),
    context_uri             String,
    _ingested_at            DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (track_id, captured_at);

-- Kafka engine consumer table — schema must match the JSON message keys
-- emitted by ingestion/spotify/producer_current.py.
CREATE TABLE IF NOT EXISTS bronze.kafka_spotify_player_current (
    captured_at             DateTime64(3),
    track_id                String,
    track_name              String,
    track_uri               String,
    track_duration_ms       Int32,
    progress_ms             Int32,
    is_playing              Bool,
    album_id                String,
    album_name              String,
    album_uri               String,
    album_images            Array(String),
    artists_ids             Array(String),
    artists_names           Array(String),
    device_id               String,
    device_name             String,
    device_type             String,
    device_volume_percent   Int32,
    context_type            String,
    context_uri             String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'redpanda:9092',
    kafka_topic_list = 'spotify.player.current',
    kafka_group_name = 'clickhouse_spotify_current',
    kafka_format = 'JSONEachRow',
    kafka_skip_broken_messages = 1;

-- Pump Kafka → storage.
CREATE MATERIALIZED VIEW IF NOT EXISTS bronze.mv_spotify_player_current
TO bronze.spotify_player_current AS
SELECT
    captured_at,
    track_id,
    track_name,
    track_uri,
    track_duration_ms,
    progress_ms,
    is_playing,
    album_id,
    album_name,
    album_uri,
    album_images,
    artists_ids,
    artists_names,
    device_id,
    device_name,
    device_type,
    device_volume_percent,
    context_type,
    context_uri
FROM bronze.kafka_spotify_player_current;

-- ── Dead-letter landing ────────────────────────────────────────────────────
-- Producer-side schema rejects, wrapped in an envelope (rejected_at / topic /
-- error / payload — keys produced by dlq_envelope() in producer_current.py).
-- ReplacingMergeTree on the full envelope: Kafka at-least-once redelivery and
-- R2 restores dedup for free. Rides the nightly warehouse_r2_archive like
-- every bronze storage table.

CREATE TABLE IF NOT EXISTS bronze.spotify_player_current_dlq (
    rejected_at    DateTime64(3),
    topic          LowCardinality(String),
    error          String,
    payload        String,
    _ingested_at   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (rejected_at, error, payload);

-- The envelope is always producer-built valid JSON; kafka_skip_broken_messages
-- stays on as the guard against hand-produced garbage stalling the consumer.
CREATE TABLE IF NOT EXISTS bronze.kafka_spotify_player_current_dlq (
    rejected_at    DateTime64(3),
    topic          String,
    error          String,
    payload        String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'redpanda:9092',
    kafka_topic_list = 'spotify.player.current.dlq',
    kafka_group_name = 'clickhouse_spotify_current_dlq',
    kafka_format = 'JSONEachRow',
    kafka_skip_broken_messages = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS bronze.mv_spotify_player_current_dlq
TO bronze.spotify_player_current_dlq AS
SELECT
    rejected_at,
    topic,
    error,
    payload
FROM bronze.kafka_spotify_player_current_dlq;
