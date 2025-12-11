{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Home Recent Events

    Aggregates recent events from all sources for the home page dashboard.
    Shows last 10 events per source with formatted display data.

    Dashboard Use:
    - Recent Events section on home page
*/

WITH spotify_events AS (
    SELECT
        track,
        artist,
        played_at,
        album_art,
        relative_time,
        recency_rank
    FROM {{ ref('gold_spotify_recent_tracks') }}
    WHERE recency_rank <= 10
),

youtube_events AS (
    SELECT
        title,
        activity_type,
        time,
        is_from_ads,
        relative_time,
        recency_rank
    FROM {{ ref('gold_youtube_recent_videos') }}
    WHERE recency_rank <= 10
),

maps_events AS (
    SELECT
        location,
        type,
        time,
        timeOfDay,
        ROW_NUMBER() OVER (ORDER BY activity_time_raw DESC) AS recency_rank
    FROM {{ ref('gold_maps_recent_activities') }}
    LIMIT 10
)

SELECT
    'spotify' AS source,
    s.recency_rank,
    s.track AS title,
    s.artist AS subtitle,
    s.played_at AS time,
    s.album_art AS image_url,
    '' AS activity_type,
    s.relative_time AS metadata,
    0 AS is_from_ads
FROM spotify_events s

UNION ALL

SELECT
    'youtube' AS source,
    y.recency_rank,
    y.title AS title,
    y.relative_time AS subtitle,
    y.time AS time,
    '' AS image_url,
    y.activity_type AS activity_type,
    '' AS metadata,
    y.is_from_ads
FROM youtube_events y

UNION ALL

SELECT
    'maps' AS source,
    m.recency_rank,
    m.location AS title,
    m.type AS subtitle,
    m.time AS time,
    '' AS image_url,
    m.type AS activity_type,
    m.timeOfDay AS metadata,
    0 AS is_from_ads
FROM maps_events m

ORDER BY source, recency_rank
