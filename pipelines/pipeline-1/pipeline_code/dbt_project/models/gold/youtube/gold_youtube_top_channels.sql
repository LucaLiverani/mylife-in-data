{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Top YouTube Channels

    Top channels by watch count and total watch time.
    Shows the channels you watch most frequently with engagement metrics.
*/

WITH deduplicated_watches AS (
    -- Remove duplicate rows (same video watched on same date)
    SELECT DISTINCT
        channel_id,
        channel_title,
        video_id,
        activity_date,
        duration_seconds,
        view_count,
        like_count,
        comment_count,
        like_rate_percent,
        category_name
    FROM {{ ref('silver_youtube_watch_history_enriched') }}
    WHERE
        activity_type = 'watched'
        AND channel_id != ''
        AND channel_title != ''
        AND is_enriched = 1
),

channel_date_ranges AS (
    -- Get first and last watched date per channel
    SELECT
        channel_id,
        channel_title,
        MIN(activity_date) AS first_watched,
        MAX(activity_date) AS last_watched
    FROM deduplicated_watches
    GROUP BY channel_id, channel_title
),

unique_videos_per_channel AS (
    -- Get unique videos per channel with their metrics
    SELECT
        channel_id,
        channel_title,
        video_id,
        any(duration_seconds) AS duration_seconds,
        any(view_count) AS view_count,
        any(like_count) AS like_count,
        any(comment_count) AS comment_count,
        any(like_rate_percent) AS like_rate_percent,
        any(category_name) AS category_name
    FROM deduplicated_watches
    GROUP BY channel_id, channel_title, video_id
)

SELECT
    -- Channel identification
    uv.channel_id,
    uv.channel_title,

    -- Watch metrics (count unique videos, not watch events)
    COUNT(*) AS watch_count,
    SUM(uv.duration_seconds * 0.6) AS total_watch_time_seconds,  -- Apply 60% completion rate
    AVG(uv.duration_seconds) AS avg_video_duration_seconds,

    -- Format total watch time
    concat(
        toString(intDiv(SUM(uv.duration_seconds * 0.6), 3600)), 'h ',
        toString(intDiv(toInt64(SUM(uv.duration_seconds * 0.6)) % 3600, 60)), 'm'
    ) AS total_watch_time_formatted,

    -- Format average duration
    concat(
        toString(intDiv(AVG(uv.duration_seconds), 60)), 'm ',
        toString(toInt64(AVG(uv.duration_seconds)) % 60), 's'
    ) AS avg_duration_formatted,

    -- Engagement metrics (averages across all watched videos from this channel)
    AVG(uv.view_count) AS avg_view_count,
    AVG(uv.like_count) AS avg_like_count,
    AVG(uv.comment_count) AS avg_comment_count,
    AVG(uv.like_rate_percent) AS avg_like_rate,

    -- Most common category for this channel (using any since channels typically have one category)
    any(uv.category_name) AS primary_category,

    -- Date range
    any(dr.first_watched) AS first_watched,
    any(dr.last_watched) AS last_watched,

    -- Video variety (this equals watch_count now since we're counting unique videos)
    COUNT(DISTINCT uv.video_id) AS unique_videos_watched

FROM unique_videos_per_channel uv
LEFT JOIN channel_date_ranges dr ON uv.channel_id = dr.channel_id AND uv.channel_title = dr.channel_title
GROUP BY
    uv.channel_id,
    uv.channel_title
ORDER BY total_watch_time_seconds DESC
