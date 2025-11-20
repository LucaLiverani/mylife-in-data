{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    Silver Layer: Spotify Tracks

    Cleans and deduplicates raw track data from bronze layer.
    - Removes duplicates based on played_at timestamp
    - Standardizes data types
    - Filters out invalid/test data
*/

WITH raw_tracks AS (
    SELECT
        -- Track information
        track_id,
        track_name,
        track_uri,
        track_popularity,
        track_duration_ms,
        track_explicit,
        track_preview_url,
        isrc,

        -- Album information
        album_id,
        album_name,
        album_type,
        album_release_date,
        album_uri,

        -- Primary artist (first in array)
        artist_id,
        artist_name,
        artist_uri,

        -- All artists (for multi-artist tracks)
        artists_ids,
        artists_names,

        -- Context (where it was played)
        context_type,
        context_uri,

        -- Playback timestamp
        played_at,

        -- Metadata
        ingested_at,
        execution_date,
        dag_id,
        run_id,
        source,

        -- Deduplication: keep most recent ingestion
        ROW_NUMBER() OVER (
            PARTITION BY played_at, track_id
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM bronze.raw_spotify_tracks
    WHERE
        -- Filter out invalid data
        track_id != ''
        AND track_name != ''
        AND artist_id != ''
        AND played_at IS NOT NULL
)

SELECT
    -- Track info
    track_id,
    track_name,
    track_uri,
    track_popularity,
    track_duration_ms,
    ROUND(track_duration_ms / 1000.0, 2) AS track_duration_seconds,
    ROUND(track_duration_ms / 1000.0 / 60.0, 2) AS track_duration_minutes,
    track_explicit,
    track_preview_url,
    isrc,

    -- Album info
    album_id,
    album_name,
    album_type,
    album_release_date,
    album_uri,

    -- Artist info
    artist_id,
    artist_name,
    artist_uri,
    artists_ids,
    artists_names,

    -- Context
    context_type,
    context_uri,

    -- Playback info
    played_at,
    toDate(played_at) AS played_date,
    toHour(played_at) AS played_hour,
    toDayOfWeek(played_at) AS day_of_week,
    toStartOfWeek(played_at) AS week_start,
    toStartOfMonth(played_at) AS month_start,

    -- Metadata
    ingested_at,
    execution_date,
    dag_id,
    run_id,
    source

FROM raw_tracks
WHERE row_num = 1  -- Keep only the most recent version
