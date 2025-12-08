{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Activity Type Breakdown

    Breakdown of YouTube activities by type (watched, search, etc.).
    Shows distribution of different interaction types.

    Dashboard Use:
    - Activity type pie/donut chart
    - Category distribution visualization
*/

WITH activity_counts AS (
    SELECT
        activity_type,
        COUNT(*) AS activity_count,
        COUNT(DISTINCT video_id) AS unique_videos,
        COUNT(DISTINCT activity_date) AS unique_days,
        MIN(activity_time) AS first_activity,
        MAX(activity_time) AS last_activity
    FROM {{ ref('silver_youtube_watch_history') }}
    WHERE activity_type != ''
    GROUP BY activity_type
),

total_activities AS (
    SELECT SUM(activity_count) AS total
    FROM activity_counts
)

SELECT
    ac.activity_type,
    ac.activity_count,
    ac.unique_videos,
    ac.unique_days,
    ac.first_activity,
    ac.last_activity,

    -- Calculate percentage
    round(ac.activity_count / t.total * 100, 1) AS percentage,

    -- Ranking
    ROW_NUMBER() OVER (ORDER BY ac.activity_count DESC) AS rank,

    -- Category display name
    CASE ac.activity_type
        WHEN 'watched' THEN 'Videos Watched'
        WHEN 'search' THEN 'Searches'
        WHEN 'visit' THEN 'Channel Visits'
        WHEN 'subscribe' THEN 'Subscriptions'
        WHEN 'like' THEN 'Likes'
        WHEN 'comment' THEN 'Comments'
        WHEN 'share' THEN 'Shares'
        ELSE initCap(ac.activity_type)
    END AS display_name,

    -- Metadata
    now() AS updated_at

FROM activity_counts ac
CROSS JOIN total_activities t
ORDER BY ac.activity_count DESC
