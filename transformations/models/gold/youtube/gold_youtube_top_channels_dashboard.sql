{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Dashboard View: Top YouTube Channels

    Top 20 channels for dashboard display.
*/

SELECT
    channel_id,
    channel_title,
    watch_count,
    total_watch_time_seconds,
    total_watch_time_formatted,
    avg_video_duration_seconds,
    avg_duration_formatted,
    avg_view_count,
    avg_like_count,
    avg_like_rate,
    primary_category,
    first_watched,
    last_watched,
    unique_videos_watched
FROM {{ ref('gold_youtube_top_channels') }}
LIMIT 20
