-- ============================================================================
-- Spotify Artists Dimension Table
-- ============================================================================
-- This table tracks the current state of each artist for deduplication
-- and refresh logic. Used by the artist ingestion DAG to determine which
-- artists need to be fetched or refreshed.
-- ============================================================================

-- 0. Ensure spotify database exists
CREATE DATABASE IF NOT EXISTS spotify;

-- 1. Drop existing table if needed
DROP TABLE IF EXISTS spotify.spotify_artists;
DROP TABLE IF EXISTS spotify.mv_spotify_artists_dimension;

-- 2. Create artists dimension table with deduplication
CREATE TABLE spotify.spotify_artists (
    -- Artist identification
    artist_id String,
    artist_name String,
    artist_uri String,

    -- Artist metrics
    popularity UInt16,
    followers_total UInt32,

    -- Metadata
    genres Array(String),
    image_url String,
    external_url_spotify String,

    -- Tracking
    last_updated DateTime,
    first_discovered DateTime,
    update_count UInt32 DEFAULT 1
) ENGINE = ReplacingMergeTree(last_updated)
ORDER BY artist_id
PRIMARY KEY artist_id
SETTINGS index_granularity = 8192;

-- ============================================================================
-- Materialized View to populate from raw_spotify_artists
-- ============================================================================
-- This view automatically updates the dimension table when new raw data arrives

CREATE MATERIALIZED VIEW spotify.mv_spotify_artists_dimension
TO spotify.spotify_artists AS
SELECT
    artist_id,
    artist_name,
    artist_uri,
    popularity,
    followers_total,
    genres,
    image_url,
    external_url_spotify,
    toDateTime(ingested_at) AS last_updated,
    toDateTime(ingested_at) AS first_discovered,
    1 AS update_count
FROM bronze.raw_spotify_artists;

-- ============================================================================
-- Helper Queries
-- ============================================================================

-- Get artists needing refresh (older than 7 days)
-- SELECT artist_id, artist_name, last_updated
-- FROM spotify.spotify_artists
-- WHERE last_updated < now() - toIntervalDay(7)
-- ORDER BY last_updated ASC
-- LIMIT 1000;

-- Get artist statistics
-- SELECT
--     count() AS total_artists,
--     min(last_updated) AS oldest_update,
--     max(last_updated) AS newest_update,
--     avg(followers_total) AS avg_followers,
--     max(followers_total) AS max_followers
-- FROM spotify.spotify_artists;

-- Top artists by followers
-- SELECT
--     artist_name,
--     followers_total,
--     popularity,
--     arrayStringConcat(genres, ', ') AS genres_list,
--     last_updated
-- FROM spotify.spotify_artists
-- ORDER BY followers_total DESC
-- LIMIT 20;

-- Check update frequency
-- SELECT
--     toDate(last_updated) AS update_date,
--     count() AS artists_updated
-- FROM spotify.spotify_artists
-- GROUP BY update_date
-- ORDER BY update_date DESC
-- LIMIT 30;
