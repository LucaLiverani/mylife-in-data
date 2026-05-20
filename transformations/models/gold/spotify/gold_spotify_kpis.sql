{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Spotify KPIs

    Pre-calculated key performance indicators for the dashboard.
    Single row with all KPI metrics.
*/

WITH track_stats AS (
    SELECT
        COUNT(*) AS total_plays,
        COUNT(DISTINCT track_id) AS unique_tracks,
        COUNT(DISTINCT artist_id) AS unique_artists,
        COUNT(DISTINCT album_id) AS unique_albums,
        SUM(track_duration_ms) AS total_duration_ms,
        MIN(played_at) AS first_play,
        MAX(played_at) AS last_play
    FROM {{ ref('silver_spotify_tracks') }}
),

daily_stats AS (
    SELECT
        AVG(daily_duration_ms) AS avg_daily_duration_ms,
        AVG(daily_plays) AS avg_daily_plays
    FROM (
        SELECT
            played_date,
            SUM(track_duration_ms) AS daily_duration_ms,
            COUNT(*) AS daily_plays
        FROM {{ ref('silver_spotify_tracks') }}
        GROUP BY played_date
    )
)

SELECT
    -- Total counts
    formatReadableQuantity(total_plays) AS songs_streamed,
    formatReadableQuantity(unique_tracks) AS unique_songs,
    formatReadableQuantity(unique_artists) AS unique_artists,
    formatReadableQuantity(unique_albums) AS unique_albums,

    -- Time metrics
    concat(
        toString(ROUND(total_duration_ms / 1000.0 / 3600.0)),
        ' hrs'
    ) AS total_time,

    concat(
        toString(ROUND(avg_daily_duration_ms / 1000.0 / 3600.0, 1)),
        ' hrs'
    ) AS avg_daily,

    -- Raw values for calculations
    total_plays AS total_plays_raw,
    unique_artists AS unique_artists_raw,
    total_duration_ms,
    avg_daily_duration_ms,
    avg_daily_plays,

    -- Date range
    first_play,
    last_play,
    dateDiff('day', first_play, last_play) + 1 AS days_tracked,

    -- Metadata
    now() AS updated_at

FROM track_stats
CROSS JOIN daily_stats
