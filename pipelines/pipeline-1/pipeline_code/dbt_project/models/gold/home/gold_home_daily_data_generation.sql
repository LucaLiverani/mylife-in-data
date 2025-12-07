{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Home - Daily Data Generation

    Aggregates daily data generation from all available sources for the
    "Data Generation Over Time" chart on the home page.

    Combines:
    - Spotify: Daily play counts
    - Google Maps: Total daily activities

    Dashboard Use:
    - Powers the main data generation chart on the home/overview page.
*/

WITH spotify_daily AS (
    SELECT
        toDate(date) AS date,
        play_count AS spotify_plays
    FROM {{ ref('gold_spotify_daily_listening') }}
),

maps_daily AS (
    SELECT
        activity_date AS date,
        total_activities AS maps_activities
    FROM {{ ref('gold_maps_daily_activity_breakdown') }}
),

all_sources AS (
    SELECT
        COALESCE(s.date, m.date) AS date,
        s.spotify_plays,
        m.maps_activities
    FROM spotify_daily s
    FULL OUTER JOIN maps_daily m ON s.date = m.date
)

SELECT
    toString(date) AS date,
    
    -- Individual source counts (coalesce to 0 if null)
    COALESCE(spotify_plays, 0) AS spotify,
    COALESCE(maps_activities, 0) AS maps,
    
    -- Hardcoded placeholders for future sources
    0 AS youtube,
    0 AS google,

    -- Total daily events
    COALESCE(spotify_plays, 0) + COALESCE(maps_activities, 0) AS total_events,

    now() AS updated_at

FROM all_sources
ORDER BY date DESC
