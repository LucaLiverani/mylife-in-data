{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Recent Videos Dashboard View

    Pre-formatted view of recent videos for dashboard timeline.
    Limited to last 20 for performance.

    Dashboard Use:
    - Simple SELECT * query
    - Recent activity timeline display
*/

SELECT
    video_id,
    title,
    title_url,
    time,
    date,
    time_of_day,
    day_name,
    activity_type,
    description,
    is_from_ads,
    relative_time

FROM {{ ref('gold_youtube_recent_videos') }}
WHERE recency_rank <= 20
ORDER BY recency_rank
