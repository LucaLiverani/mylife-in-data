{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Dashboard View: YouTube Category Breakdown

    Category breakdown for dashboard display.
*/

SELECT
    category_name,
    watch_count,
    total_watch_time_seconds,
    total_watch_time_formatted,
    watch_percentage,
    time_percentage,
    avg_video_duration_seconds,
    avg_view_count,
    avg_like_rate,
    unique_channels,
    unique_videos
FROM {{ ref('gold_youtube_category_breakdown') }}
ORDER BY watch_count DESC
