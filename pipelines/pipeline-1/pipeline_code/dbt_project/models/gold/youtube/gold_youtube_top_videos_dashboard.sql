{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Top Videos Dashboard View

    Pre-formatted view of top videos for dashboard display.
    Limited to top 10 for charts and lists.

    Dashboard Use:
    - Simple SELECT * query
    - Top videos bar chart
    - Most watched videos list
*/

SELECT
    rank,
    video_id,
    title,
    title_url,
    watch_count,
    unique_days_watched,
    frequency_category,
    is_from_ads

FROM {{ ref('gold_youtube_top_videos') }}
WHERE rank <= 10
ORDER BY rank
