{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Watch Time Dashboard View (Last 30 Days)

    Pre-filtered and formatted view of daily watch activity for dashboard charts.
    Shows only the last 30 days.

    Dashboard Use:
    - Simple SELECT * query
    - Date formatted as string
    - Last 30 days only
*/

SELECT
    -- Date formatted as string
    date,

    -- Main metric: videos watched (proxy for watch time)
    videos_watched,

    -- Additional metrics
    unique_videos,
    watched_count,
    search_count

FROM {{ ref('gold_youtube_daily_watch_time') }}
WHERE toDate(date) >= today() - 30
ORDER BY date ASC
