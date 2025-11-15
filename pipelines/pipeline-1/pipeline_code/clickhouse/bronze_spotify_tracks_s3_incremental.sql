-- ============================================================================
-- S3Queue: Automatic File Processing for Spotify Tracks
-- ============================================================================
-- This automatically processes new files as they arrive in S3
-- Requires ClickHouse 23.3+ and ZooKeeper/ClickHouse Keeper for coordination
-- ============================================================================

-- 0. Ensure bronze database exists
CREATE DATABASE IF NOT EXISTS bronze;


DROP TABLE IF EXISTS bronze.raw_spotify_tracks;
DROP TABLE IF EXISTS bronze.s3queue_spotify_tracks;
DROP TABLE IF EXISTS bronze.mv_s3queue_spotify_tracks;

-- 1. Create target table for processed data (persistent storage)
CREATE TABLE bronze.raw_spotify_tracks (
    -- Track info (extracted from nested JSON)
    track_id String,
    track_name String,
    track_uri String,
    track_popularity UInt16,
    track_duration_ms UInt32,
    track_explicit Bool,
    track_preview_url String,
    isrc String,

    -- Album info
    album_id String,
    album_name String,
    album_type String,
    album_release_date Nullable(Date),
    album_uri String,

    -- Artist info (first artist)
    artist_id String,
    artist_name String,
    artist_uri String,

    -- All artists as array (for multi-artist tracks)
    artists_ids Array(String),
    artists_names Array(String),

    -- Context (playlist/album where it was played)
    context_type String,
    context_uri String,

    -- Playback info
    played_at DateTime64(3),

    -- Ingestion metadata
    ingested_at DateTime64(6),
    execution_date DateTime,
    dag_id String,
    run_id String,
    source String,

    -- Store complete raw JSON for reference
    raw_json String

) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(played_at)
ORDER BY (track_id, played_at)
SETTINGS index_granularity = 8192;

-- 2. Create S3Queue table (watches for new files in S3)
-- Note: Files are stored as gzipped JSONL in inbound/raw/spotify/api/tracks/
-- Using LineAsString format to read each JSON line as a string for parsing
CREATE TABLE IF NOT EXISTS bronze.s3queue_spotify_tracks (
    raw_json String
) ENGINE = S3Queue(
    'http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz',
    'admin',
    'minio08062013',
    'LineAsString'
)
SETTINGS
    mode = 'ordered',                    -- Process files in order
    keeper_path = '/clickhouse/s3queue/spotify_api_tracks',  -- Keeper path for coordination
    s3queue_processing_threads_num = 4,  -- Parallel processing threads
    s3queue_polling_min_timeout_ms = 1000,
    s3queue_polling_max_timeout_ms = 10000;

-- 3. Create materialized view to auto-process new files
CREATE MATERIALIZED VIEW IF NOT EXISTS bronze.mv_s3queue_spotify_tracks TO bronze.raw_spotify_tracks AS
SELECT
    JSONExtractString(raw_json, 'raw_item', 'track', 'id') AS track_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'name') AS track_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'uri') AS track_uri,
    JSONExtractUInt(raw_json, 'raw_item', 'track', 'popularity') AS track_popularity,
    JSONExtractUInt(raw_json, 'raw_item', 'track', 'duration_ms') AS track_duration_ms,
    JSONExtractBool(raw_json, 'raw_item', 'track', 'explicit') AS track_explicit,
    JSONExtractString(raw_json, 'raw_item', 'track', 'preview_url') AS track_preview_url,
    JSONExtractString(raw_json, 'raw_item', 'track', 'external_ids', 'isrc') AS isrc,

    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'id') AS album_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'name') AS album_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'album_type') AS album_type,
    toDate(parseDateTimeBestEffortOrNull(JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'release_date'))) AS album_release_date,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'uri') AS album_uri,

    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'id') AS artist_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'name') AS artist_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'uri') AS artist_uri,

    arrayMap(x -> JSONExtractString(x, 'id'),
             JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_item', 'track', 'artists'))) AS artists_ids,
    arrayMap(x -> JSONExtractString(x, 'name'),
             JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_item', 'track', 'artists'))) AS artists_names,

    JSONExtractString(raw_json, 'raw_item', 'context', 'type') AS context_type,
    JSONExtractString(raw_json, 'raw_item', 'context', 'uri') AS context_uri,

    parseDateTime64BestEffort(JSONExtractString(raw_json, 'raw_item', 'played_at')) AS played_at,

    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'execution_date')) AS execution_date,
    JSONExtractString(raw_json, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'source') AS source,

    raw_json AS raw_json

FROM bronze.s3queue_spotify_tracks;


-- ============================================================================
-- Monitoring & Debugging Queries
-- ============================================================================

-- Check S3Queue processing status
-- SELECT * FROM system.s3queue_log
-- ORDER BY event_time DESC
-- LIMIT 20;

-- Check which files have been processed
-- SELECT
--     file_name,
--     status,
--     rows_processed,
--     processing_start_time,
--     processing_end_time,
--     exception
-- FROM system.s3queue
-- WHERE table = 's3queue_spotify_tracks'
-- ORDER BY processing_start_time DESC;

-- Count processed records
-- SELECT count(*) as total_tracks,
--        min(played_at) as earliest_play,
--        max(played_at) as latest_play,
--        count(DISTINCT track_id) as unique_tracks
-- FROM bronze.raw_spotify_tracks;

-- Check recent ingestions
-- SELECT
--     source,
--     dag_id,
--     execution_date,
--     count(*) as records
-- FROM bronze.raw_spotify_tracks
-- GROUP BY source, dag_id, execution_date
-- ORDER BY execution_date DESC
-- LIMIT 10;

-- View ZooKeeper coordination state
-- SELECT * FROM system.zookeeper
-- WHERE path = '/clickhouse/s3queue/spotify_tracks';
