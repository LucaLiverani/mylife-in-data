{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: YouTube KPIs with Watch Time

    Comprehensive KPIs including watch time metrics from enriched data.
    Combines activity counts with actual video duration data.
*/

WITH enriched_stats AS (
    SELECT
        -- Total activities (enriched only)
        COUNT(*) AS total_enriched_activities,
        countIf(activity_type = 'watched') AS total_watched_enriched,

        -- Watch time metrics
        SUM(CASE WHEN activity_type = 'watched' THEN duration_seconds ELSE 0 END) AS total_watch_time_seconds,
        AVG(CASE WHEN activity_type = 'watched' THEN duration_seconds ELSE NULL END) AS avg_watch_time_seconds,

        -- Unique counts
        COUNT(DISTINCT channel_id) AS unique_channels,
        COUNT(DISTINCT video_id) AS unique_videos,
        COUNT(DISTINCT category_name) AS unique_categories,

        -- Engagement
        AVG(view_count) AS avg_view_count,
        AVG(like_count) AS avg_like_count,
        AVG(like_rate_percent) AS avg_like_rate

    FROM {{ ref('silver_youtube_watch_history_enriched') }}
    WHERE is_enriched = 1
),

all_stats AS (
    SELECT
        -- All activities (including non-enriched)
        COUNT(*) AS total_activities,
        countIf(activity_type = 'watched') AS total_watched,
        countIf(activity_type = 'search') AS total_searches,
        countIf(activity_type = 'visit') AS total_visits,
        countIf(is_from_ads = 1) AS total_ads_watched,
        countIf(activity_type NOT IN ('watched', 'search', 'visit')) AS total_other,

        -- Date range
        MIN(activity_date) AS first_activity_date,
        MAX(activity_date) AS last_activity_date,
        COUNT(DISTINCT activity_date) AS total_days_tracked

    FROM {{ ref('silver_youtube_watch_history') }}
)

SELECT
    -- Activity counts (all data)
    all_stats.total_activities,
    all_stats.total_watched AS videos_watched,
    all_stats.total_searches,
    all_stats.total_visits,
    all_stats.total_ads_watched,
    all_stats.total_other,

    -- Watch time metrics (enriched data only)
    enriched_stats.total_watch_time_seconds,
    enriched_stats.avg_watch_time_seconds,

    -- Format watch time
    concat(
        toString(intDiv(enriched_stats.total_watch_time_seconds, 3600)), 'h ',
        toString(intDiv(enriched_stats.total_watch_time_seconds % 3600, 60)), 'm'
    ) AS total_watch_time_formatted,

    concat(
        toString(intDiv(toInt64(enriched_stats.avg_watch_time_seconds), 60)), 'm ',
        toString(toInt64(enriched_stats.avg_watch_time_seconds) % 60), 's'
    ) AS avg_watch_time_formatted,

    -- Unique content (enriched)
    enriched_stats.unique_channels,
    enriched_stats.unique_videos,
    enriched_stats.unique_categories,

    -- Engagement metrics (enriched)
    enriched_stats.avg_view_count,
    enriched_stats.avg_like_count,
    enriched_stats.avg_like_rate,

    -- Date range
    all_stats.first_activity_date,
    all_stats.last_activity_date,
    all_stats.total_days_tracked,

    -- Daily averages
    ROUND(all_stats.total_activities / all_stats.total_days_tracked, 1) AS avg_activities_per_day,
    ROUND(all_stats.total_watched / all_stats.total_days_tracked, 1) AS avg_watched_per_day,
    ROUND(enriched_stats.total_watch_time_seconds / all_stats.total_days_tracked, 0) AS avg_watch_time_per_day_seconds,

    -- Ads percentage
    ROUND(all_stats.total_ads_watched * 100.0 / all_stats.total_watched, 1) AS ads_percentage,

    -- Enrichment coverage
    ROUND(enriched_stats.total_enriched_activities * 100.0 / all_stats.total_activities, 1) AS enrichment_percentage

FROM all_stats, enriched_stats
