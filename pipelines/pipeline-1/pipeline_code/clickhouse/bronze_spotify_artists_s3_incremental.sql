-- ============================================================================
-- S3Queue: Automatic File Processing for Spotify Artists
-- ============================================================================
-- This automatically processes new files as they arrive in S3
-- Requires ClickHouse 23.3+ and ZooKeeper/ClickHouse Keeper for coordination
-- ============================================================================

-- 0. Ensure bronze database exists
CREATE DATABASE IF NOT EXISTS bronze;


DROP TABLE IF EXISTS bronze.raw_spotify_artists;
DROP TABLE IF EXISTS bronze.s3queue_spotify_artists;
DROP TABLE IF EXISTS bronze.mv_s3queue_spotify_artists;

-- 1. Create target table for processed data (persistent storage)
CREATE TABLE bronze.raw_spotify_artists (
    -- Artist info (extracted from nested JSON)
    artist_id String,
    artist_name String,
    artist_uri String,
    artist_type String,
    popularity UInt16,

    -- Followers
    followers_total UInt32,

    -- Genres (array)
    genres Array(String),

    -- Images (first image URL for convenience)
    image_url String,

    -- All images as array (for different sizes)
    images_urls Array(String),
    images_heights Array(UInt16),
    images_widths Array(UInt16),

    -- External URLs
    external_url_spotify String,

    -- Ingestion metadata
    ingested_at DateTime64(6),
    execution_date DateTime,
    dag_id String,
    run_id String,
    source String,
    batch_number UInt16,

    -- Store complete raw JSON for reference
    raw_json String

) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (artist_id)
SETTINGS index_granularity = 8192;

-- 2. Create S3Queue table (watches for new files in S3)
-- Note: Files are stored as JSONL in inbound/raw/spotify/api/artists/
-- Using LineAsString format to read each JSON line as a string for parsing
CREATE TABLE IF NOT EXISTS bronze.s3queue_spotify_artists (
    raw_json String
) ENGINE = S3Queue(
    'http://minio:9000/inbound/raw/spotify/api/artists/*.jsonl',
    'admin',
    'minio08062013',
    'LineAsString'
)
SETTINGS
    mode = 'ordered',                    -- Process files in order
    keeper_path = '/clickhouse/s3queue/spotify_api_artists',  -- Keeper path for coordination
    s3queue_processing_threads_num = 4,  -- Parallel processing threads
    s3queue_polling_min_timeout_ms = 1000,
    s3queue_polling_max_timeout_ms = 10000;

-- 3. Create materialized view to auto-process new files
CREATE MATERIALIZED VIEW IF NOT EXISTS bronze.mv_s3queue_spotify_artists TO bronze.raw_spotify_artists AS
SELECT
    JSONExtractString(raw_json, 'raw_artist', 'id') AS artist_id,
    JSONExtractString(raw_json, 'raw_artist', 'name') AS artist_name,
    JSONExtractString(raw_json, 'raw_artist', 'uri') AS artist_uri,
    JSONExtractString(raw_json, 'raw_artist', 'type') AS artist_type,
    JSONExtractUInt(raw_json, 'raw_artist', 'popularity') AS popularity,

    JSONExtractUInt(raw_json, 'raw_artist', 'followers', 'total') AS followers_total,

    JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'genres')) AS genres,

    -- Extract first image URL for convenience
    JSONExtractString(raw_json, 'raw_artist', 'images', 1, 'url') AS image_url,

    -- Extract all image URLs
    arrayMap(x -> JSONExtractString(x, 'url'),
             JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'images'))) AS images_urls,
    arrayMap(x -> JSONExtractUInt(x, 'height'),
             JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'images'))) AS images_heights,
    arrayMap(x -> JSONExtractUInt(x, 'width'),
             JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'images'))) AS images_widths,

    JSONExtractString(raw_json, 'raw_artist', 'external_urls', 'spotify') AS external_url_spotify,

    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'execution_date')) AS execution_date,
    JSONExtractString(raw_json, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'source') AS source,
    JSONExtractUInt(raw_json, '_ingestion_metadata', 'batch_number') AS batch_number,

    raw_json AS raw_json

FROM bronze.s3queue_spotify_artists;


-- ============================================================================
-- Monitoring & Debugging Queries
-- ============================================================================

-- Check S3Queue processing status
-- SELECT * FROM system.s3queue_log
-- WHERE table_name = 's3queue_spotify_artists'
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
-- WHERE table = 's3queue_spotify_artists'
-- ORDER BY processing_start_time DESC;

-- Count processed records
-- SELECT count(*) as total_artists,
--        min(ingested_at) as earliest_ingestion,
--        max(ingested_at) as latest_ingestion,
--        count(DISTINCT artist_id) as unique_artists
-- FROM bronze.raw_spotify_artists;

-- Check recent ingestions
-- SELECT
--     source,
--     dag_id,
--     execution_date,
--     count(*) as records,
--     count(DISTINCT artist_id) as unique_artists
-- FROM bronze.raw_spotify_artists
-- GROUP BY source, dag_id, execution_date
-- ORDER BY execution_date DESC
-- LIMIT 10;

-- View top artists by followers
-- SELECT
--     artist_name,
--     followers_total,
--     popularity,
--     genres,
--     ingested_at
-- FROM bronze.raw_spotify_artists
-- ORDER BY followers_total DESC
-- LIMIT 20;

-- View most popular genres
-- SELECT
--     genre,
--     count() as artist_count
-- FROM bronze.raw_spotify_artists
-- ARRAY JOIN genres as genre
-- GROUP BY genre
-- ORDER BY artist_count DESC
-- LIMIT 20;

-- Check for artists needing refresh (older than 7 days)
-- SELECT
--     artist_id,
--     artist_name,
--     ingested_at,
--     now() - ingested_at as age_seconds,
--     toIntervalDay(7) as refresh_threshold
-- FROM bronze.raw_spotify_artists
-- WHERE ingested_at < now() - toIntervalDay(7)
-- ORDER BY ingested_at ASC
-- LIMIT 100;

-- View ZooKeeper coordination state
-- SELECT * FROM system.zookeeper
-- WHERE path = '/clickhouse/s3queue/spotify_api_artists';