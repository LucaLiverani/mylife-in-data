{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Hourly Activity Pattern

    Aggregated watch activity by hour of day.
    Helps identify viewing patterns and peak usage times.

    Dashboard Use:
    - Hourly activity heatmap
    - Time-of-day distribution chart
*/

SELECT
    activity_hour,
    concat(toString(activity_hour), ':00') AS hour,

    -- Activity counts
    COUNT(*) AS total_activities,
    countIf(activity_type = 'watched') AS watched_count,
    countIf(activity_type = 'search') AS search_count,
    countIf(is_from_ads = 1) AS ad_views_count,

    -- Unique metrics
    COUNT(DISTINCT video_id) AS unique_videos,
    COUNT(DISTINCT activity_date) AS unique_days,

    -- Time of day classification (redundant but useful)
    any(time_of_day) AS time_of_day_label,

    -- Averages
    round(COUNT(*) / COUNT(DISTINCT activity_date), 2) AS avg_activities_per_day,

    -- Metadata
    now() AS updated_at

FROM {{ ref('silver_youtube_watch_history') }}
GROUP BY activity_hour
ORDER BY activity_hour
