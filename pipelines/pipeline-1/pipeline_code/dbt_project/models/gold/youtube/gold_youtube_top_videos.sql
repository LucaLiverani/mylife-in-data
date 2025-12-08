{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Top Videos

    Most frequently watched videos grouped by video_id.
    Note: Channel information is not available in Google Takeout YouTube history,
    so we group by video instead. This can be enhanced later with YouTube API enrichment.

    Dashboard Use:
    - Top videos list
    - Watch frequency analysis
*/

WITH video_watches AS (
    SELECT
        video_id,
        title,
        title_url,
        activity_type,
        is_from_ads,
        COUNT(*) AS watch_count,
        MIN(activity_time) AS first_watched,
        MAX(activity_time) AS last_watched,
        COUNT(DISTINCT activity_date) AS unique_days_watched
    FROM {{ ref('silver_youtube_watch_history') }}
    WHERE video_id != ''
        AND activity_type = 'watched'
    GROUP BY video_id, title, title_url, activity_type, is_from_ads
),

ranked_videos AS (
    SELECT
        video_id,
        title,
        title_url,
        watch_count,
        unique_days_watched,
        first_watched,
        last_watched,
        is_from_ads,

        -- Calculate metrics
        dateDiff('day', first_watched, last_watched) AS days_span,
        round(watch_count / unique_days_watched, 2) AS avg_watches_per_day,

        -- Ranking
        ROW_NUMBER() OVER (ORDER BY watch_count DESC) AS rank

    FROM video_watches
    WHERE watch_count > 1  -- Only include videos watched more than once
)

SELECT
    rank,
    video_id,
    title,
    title_url,
    watch_count,
    unique_days_watched,
    first_watched,
    last_watched,
    days_span,
    avg_watches_per_day,
    is_from_ads,

    -- Categorization
    CASE
        WHEN watch_count >= 10 THEN 'Very Frequent'
        WHEN watch_count >= 5 THEN 'Frequent'
        WHEN watch_count >= 3 THEN 'Regular'
        ELSE 'Occasional'
    END AS frequency_category,

    -- Metadata
    now() AS updated_at

FROM ranked_videos
ORDER BY rank
LIMIT 100
