{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Home Overview Stats View

    Pre-formatted view combining stats from multiple sources for the overview page.
    All fields renamed to match dashboard API expectations.

    Dashboard Use:
    - Simple SELECT * query for overview stats
*/

WITH spotify_stats AS (
    SELECT
        total_plays_raw AS songsStreamed,
        unique_artists_raw AS artistsListened
    FROM {{ ref('gold_spotify_kpis') }}
),

youtube_stats AS (
    SELECT
        videos_watched AS videosWatched,
        unique_channels AS youtubeChannels
    FROM {{ ref('gold_youtube_kpis_with_watch_time') }}
),

maps_stats AS (
    SELECT
        unique_destinations AS citiesVisited
    FROM {{ ref('gold_maps_kpis') }}
)

SELECT
    s.songsStreamed,
    s.artistsListened,
    y.videosWatched,
    y.youtubeChannels,
    '0' AS searchQueries,
    m.citiesVisited
FROM spotify_stats s
CROSS JOIN youtube_stats y
CROSS JOIN maps_stats m
