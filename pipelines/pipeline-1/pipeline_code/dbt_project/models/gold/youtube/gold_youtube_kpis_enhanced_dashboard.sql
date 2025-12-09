{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Enhanced KPIs Dashboard View

    Pre-formatted view optimized for dashboard consumption.
    All fields renamed to match dashboard API expectations.

    Dashboard Use:
    - Simple SELECT * query
    - All columns match dashboard field names
*/

SELECT
    -- Raw counts
    total_videos,
    total_watched,
    total_searches,
    total_visits,
    total_subscriptions,
    total_likes,
    total_comments,
    total_shares,
    total_ads_watched,
    total_activities,

    -- Averages
    avg_activities_per_day,
    avg_videos_per_day,
    ads_percentage,

    -- Formatted strings
    total_videos_formatted,
    total_watched_formatted,
    total_searches_formatted,
    total_ads_watched_formatted,

    -- Date range
    toString(first_activity_date) AS first_activity_date,
    toString(last_activity_date) AS last_activity_date,
    days_span

FROM {{ ref('gold_youtube_kpis_enhanced') }}
