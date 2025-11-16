-- ============================================================================
-- S3 View: Direct Querying of Spotify Tracks from S3
-- ============================================================================
-- This view directly queries all gzipped JSONL files as they exist in S3.
-- It bypasses S3Queue for simpler, direct access to raw data.
-- ============================================================================

-- 0. Ensure bronze database exists
CREATE DATABASE IF NOT EXISTS bronze;


DROP TABLE IF EXISTS bronze.raw_spotify_tracks;
DROP TABLE IF EXISTS bronze.s3queue_spotify_tracks;
DROP TABLE IF EXISTS bronze.mv_s3queue_spotify_tracks;

-- 1. Create a VIEW to directly query all files in S3
CREATE VIEW bronze.raw_spotify_tracks AS
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
FROM
    s3('http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz', 'admin', 'minio08062013', 'LineAsString', 'raw_json String');


-- ============================================================================
-- Monitoring & Debugging Queries
-- ============================================================================

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