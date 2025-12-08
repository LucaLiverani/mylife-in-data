{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: YouTube KPIs

    Pre-calculated key performance indicators for the YouTube dashboard.
    Single row with all KPI metrics.
*/

WITH watch_stats AS (
    SELECT
        COUNT(*) AS total_videos_watched,
        COUNT(DISTINCT video_id) AS unique_videos,
        COUNT(DISTINCT
            extractURLParameter(title_url, 'v')
        ) AS unique_videos_alt,  -- Alternative count using URL
        MIN(activity_time) AS first_watch,
        MAX(activity_time) AS last_watch,
        COUNT(DISTINCT activity_date) AS days_with_activity,

        -- Activity type breakdown
        countIf(activity_type = 'watched') AS total_watched,
        countIf(activity_type = 'search') AS total_searches,
        countIf(is_from_ads = 1) AS total_ad_views
    FROM {{ ref('silver_youtube_watch_history') }}
),

daily_stats AS (
    SELECT
        AVG(daily_watch_count) AS avg_daily_watches,
        AVG(daily_unique_videos) AS avg_daily_unique_videos
    FROM (
        SELECT
            activity_date,
            COUNT(*) AS daily_watch_count,
            COUNT(DISTINCT video_id) AS daily_unique_videos
        FROM {{ ref('silver_youtube_watch_history') }}
        GROUP BY activity_date
    )
)

SELECT
    -- Total counts (formatted)
    formatReadableQuantity(total_videos_watched) AS total_videos,
    formatReadableQuantity(unique_videos) AS unique_videos_count,
    formatReadableQuantity(total_watched) AS watched_count,
    formatReadableQuantity(total_searches) AS searches_count,
    formatReadableQuantity(total_ad_views) AS ad_views_count,

    -- Averages (formatted)
    concat(
        toString(ROUND(avg_daily_watches, 1)),
        ' videos'
    ) AS avg_daily,

    -- Raw values for calculations
    total_videos_watched AS total_videos_raw,
    unique_videos AS unique_videos_raw,
    total_watched AS total_watched_raw,
    avg_daily_watches,
    avg_daily_unique_videos,

    -- Date range
    first_watch,
    last_watch,
    dateDiff('day', first_watch, last_watch) + 1 AS days_tracked,
    days_with_activity,

    -- Percentages
    round(total_ad_views / total_videos_watched * 100, 1) AS ad_views_pct,

    -- Metadata
    now() AS updated_at

FROM watch_stats
CROSS JOIN daily_stats
