{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Enhanced YouTube KPIs

    Comprehensive KPI metrics including activity type breakdowns.
    Provides all key metrics for dashboard overview.

    Dashboard Use:
    - Main KPI cards
    - Summary statistics
*/

WITH base_stats AS (
    SELECT
        COUNT(*) AS total_activities,
        COUNT(DISTINCT video_id) AS total_videos,
        COUNT(DISTINCT activity_date) AS total_days_tracked,

        -- Activity type counts
        countIf(activity_type = 'watched') AS total_watched,
        countIf(activity_type = 'search') AS total_searches,
        countIf(activity_type = 'visit') AS total_visits,
        countIf(activity_type = 'subscribe') AS total_subscriptions,
        countIf(activity_type = 'like') AS total_likes,
        countIf(activity_type = 'comment') AS total_comments,
        countIf(activity_type = 'share') AS total_shares,

        -- Ad-related metrics
        countIf(is_from_ads = 1) AS total_ads_watched,

        -- Temporal metrics
        MIN(activity_date) AS first_activity_date,
        MAX(activity_date) AS last_activity_date

    FROM {{ ref('silver_youtube_watch_history') }}
)

SELECT
    -- Raw counts
    total_activities,
    total_videos,
    total_days_tracked,
    total_watched,
    total_searches,
    total_visits,
    total_subscriptions,
    total_likes,
    total_comments,
    total_shares,
    total_ads_watched,

    -- Calculated metrics
    ROUND(total_activities / total_days_tracked, 1) AS avg_activities_per_day,
    ROUND(total_watched / total_days_tracked, 1) AS avg_videos_per_day,
    ROUND((total_ads_watched / total_watched) * 100, 1) AS ads_percentage,

    -- Formatted strings for display
    formatReadableQuantity(total_videos) AS total_videos_formatted,
    formatReadableQuantity(total_watched) AS total_watched_formatted,
    formatReadableQuantity(total_searches) AS total_searches_formatted,
    formatReadableQuantity(total_ads_watched) AS total_ads_watched_formatted,

    -- Date range
    first_activity_date,
    last_activity_date,
    dateDiff('day', first_activity_date, last_activity_date) AS days_span,

    -- Metadata
    now() AS updated_at

FROM base_stats
