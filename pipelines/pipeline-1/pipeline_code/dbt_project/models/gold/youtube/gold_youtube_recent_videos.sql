{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Recent Videos

    Last 100 watched videos for the dashboard timeline.
    Includes activity details and temporal context.

    Dashboard Use:
    - Recent activity timeline
    - Latest watch history display
*/

WITH recent_videos AS (
    SELECT
        activity_id,
        video_id,
        title,
        title_url,
        activity_time,
        activity_date,
        activity_hour,
        time_of_day,
        day_name,
        is_weekend,
        activity_type,
        description,
        is_from_ads,
        products_list,
        details_list
    FROM {{ ref('silver_youtube_watch_history') }}
    ORDER BY activity_time DESC
    LIMIT 100
),

with_rank AS (
    SELECT
        activity_id,
        video_id,
        title,
        title_url,
        toString(activity_time) AS time,
        toString(activity_date) AS date,
        activity_hour,
        time_of_day,
        day_name,
        is_weekend,
        activity_type,
        description,
        is_from_ads,
        products_list,
        details_list,

        -- Add recency rank
        ROW_NUMBER() OVER (ORDER BY activity_time DESC) AS recency_rank,

        -- Calculate relative time
        CASE
            WHEN dateDiff('hour', activity_time, now()) < 24 THEN 'Today'
            WHEN dateDiff('hour', activity_time, now()) < 48 THEN 'Yesterday'
            WHEN dateDiff('day', activity_time, now()) < 7 THEN concat(toString(dateDiff('day', activity_time, now())), ' days ago')
            WHEN dateDiff('day', activity_time, now()) < 30 THEN concat(toString(dateDiff('week', activity_time, now())), ' weeks ago')
            ELSE concat(toString(dateDiff('month', activity_time, now())), ' months ago')
        END AS relative_time

    FROM recent_videos
)

SELECT
    activity_id,
    video_id,
    title,
    title_url,
    time,
    date,
    activity_hour,
    time_of_day,
    day_name,
    is_weekend,
    activity_type,
    description,
    is_from_ads,
    products_list,
    details_list,
    recency_rank,
    relative_time,
    now() AS updated_at

FROM with_rank
ORDER BY recency_rank
