-- ============================================================================
-- S3 View: Direct Querying of Spotify Artists from S3
-- ============================================================================
-- This view directly queries all JSONL files as they exist in S3.
-- It bypasses S3Queue for simpler, direct access to raw data.
-- ============================================================================

-- 0. Ensure bronze database exists
CREATE DATABASE IF NOT EXISTS bronze;


DROP VIEW IF EXISTS bronze.raw_spotify_artists;
DROP TABLE IF EXISTS bronze.s3queue_spotify_artists;
DROP TABLE IF EXISTS bronze.mv_s3queue_spotify_artists;

-- 1. Create a VIEW to directly query all files in S3
CREATE VIEW bronze.raw_spotify_artists AS
SELECT
    JSONExtractString(raw_json, 'raw_artist', 'id') AS artist_id,
    JSONExtractString(raw_json, 'raw_artist', 'name') AS artist_name,
    JSONExtractString(raw_json, 'raw_artist', 'uri') AS artist_uri,
    JSONExtractString(raw_json, 'raw_artist', 'type') AS artist_type,
    JSONExtractUInt(raw_json, 'raw_artist', 'popularity') AS popularity,

    JSONExtractUInt(raw_json, 'raw_artist', 'followers', 'total') AS followers_total,

    JSONExtract(raw_json, 'raw_artist', 'genres', 'Array(String)') AS genres,

    -- Extract first image URL for convenience
    JSONExtractString(raw_json, 'raw_artist', 'images', 1, 'url') AS image_url,

    -- Extract all image URLs
    arrayMap(x -> JSONExtractString(x, 'url'), JSONExtract(raw_json, 'raw_artist', 'images', 'Array(String)')) AS images_urls,
    arrayMap(x -> JSONExtractUInt(x, 'height'), JSONExtract(raw_json, 'raw_artist', 'images', 'Array(String)')) AS images_heights,
    arrayMap(x -> JSONExtractUInt(x, 'width'), JSONExtract(raw_json, 'raw_artist', 'images', 'Array(String)')) AS images_widths,

    JSONExtractString(raw_json, 'raw_artist', 'external_urls', 'spotify') AS external_url_spotify,

    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, '_ingestion_metadata', 'execution_date')) AS execution_date,
    JSONExtractString(raw_json, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'source') AS source,
    JSONExtractUInt(raw_json, '_ingestion_metadata', 'batch_number') AS batch_number,

    raw_json AS raw_json
FROM
    s3('http://minio:9000/inbound/raw/spotify/api/artists/*.jsonl', 'admin', 'minio08062013', 'LineAsString', 'raw_json String');


-- ============================================================================
-- Monitoring & Debugging Queries
-- ============================================================================

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
