{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: YouTube Watch Time by Category

    Breakdown of watch activity by video category.
    Shows which types of content you watch most.
*/

SELECT
    -- Category
    category_name,
    category_id,

    -- Watch metrics
    COUNT(*) AS watch_count,
    SUM(duration_seconds) AS total_watch_time_seconds,
    AVG(duration_seconds) AS avg_video_duration_seconds,

    -- Format total watch time
    concat(
        toString(intDiv(SUM(duration_seconds), 3600)), 'h ',
        toString(intDiv(SUM(duration_seconds) % 3600, 60)), 'm'
    ) AS total_watch_time_formatted,

    -- Percentage of total watches
    round(
        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM {{ ref('silver_youtube_watch_history_enriched') }} WHERE activity_type = 'watched' AND is_enriched = 1),
        2
    ) AS watch_percentage,

    -- Percentage of total watch time
    round(
        SUM(duration_seconds) * 100.0 / (SELECT SUM(duration_seconds) FROM {{ ref('silver_youtube_watch_history_enriched') }} WHERE activity_type = 'watched' AND is_enriched = 1),
        2
    ) AS time_percentage,

    -- Engagement metrics
    AVG(view_count) AS avg_view_count,
    AVG(like_rate_percent) AS avg_like_rate,

    -- Unique content
    COUNT(DISTINCT channel_id) AS unique_channels,
    COUNT(DISTINCT video_id) AS unique_videos

FROM {{ ref('silver_youtube_watch_history_enriched') }}
WHERE
    activity_type = 'watched'
    AND category_name != ''
    AND is_enriched = 1
GROUP BY
    category_name,
    category_id
ORDER BY watch_count DESC
