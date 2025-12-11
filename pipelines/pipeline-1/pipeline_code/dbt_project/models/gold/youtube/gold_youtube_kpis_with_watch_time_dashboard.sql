{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Dashboard View: YouTube KPIs with Watch Time

    KPIs for dashboard display.
*/

SELECT
    -- Activity counts
    total_activities,
    videos_watched,
    total_searches,
    total_visits,
    total_ads_watched,

    -- Watch time
    total_watch_time_seconds,
    total_watch_time_formatted,
    avg_watch_time_seconds,
    avg_watch_time_formatted,

    -- Unique content
    unique_channels,
    unique_videos,
    unique_categories,

    -- Daily averages
    avg_activities_per_day,
    avg_watched_per_day,
    avg_watch_time_per_day_seconds,

    -- Percentages
    ads_percentage,
    enrichment_percentage,

    -- Engagement
    avg_view_count,
    avg_like_count,
    avg_like_rate,

    -- Date range
    first_activity_date,
    last_activity_date,
    total_days_tracked

FROM {{ ref('gold_youtube_kpis_with_watch_time') }}
