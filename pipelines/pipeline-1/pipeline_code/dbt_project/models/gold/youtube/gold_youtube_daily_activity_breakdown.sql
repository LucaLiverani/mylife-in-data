{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Activity Breakdown by Type

    Daily time series with separate counts for each activity type.
    Enables multi-line charts showing activity patterns over time.

    Dashboard Use:
    - Multi-line daily activity chart
    - Activity type trends over time
*/

WITH daily_breakdown AS (
    SELECT
        activity_date AS date,

        -- Count by activity type
        countIf(activity_type = 'watched') AS watched,
        countIf(activity_type = 'search') AS searches,
        countIf(activity_type = 'visit') AS visits,
        countIf(activity_type = 'subscribe') AS subscriptions,
        countIf(activity_type = 'like') AS likes,
        countIf(activity_type = 'comment') AS comments,
        countIf(activity_type = 'share') AS shares,

        -- Ads breakdown
        countIf(is_from_ads = 1) AS ads,

        -- Other activities
        countIf(activity_type NOT IN ('watched', 'search', 'visit', 'subscribe', 'like', 'comment', 'share')) AS other,

        -- Total for verification
        COUNT(*) AS total_activities,

        -- Additional context
        COUNT(DISTINCT video_id) AS unique_videos,
        COUNT(DISTINCT activity_hour) AS active_hours

    FROM {{ ref('silver_youtube_watch_history') }}
    GROUP BY activity_date
)

SELECT
    toString(date) AS date,

    -- Activity type counts
    watched,
    searches,
    visits,
    subscriptions,
    likes,
    comments,
    shares,
    ads,
    other,

    -- Totals
    total_activities,
    unique_videos,
    active_hours,

    -- Day context
    toDayOfWeek(toDate(date)) AS day_of_week,
    dateName('weekday', toDate(date)) AS day_name,

    -- Weekend flag
    CASE
        WHEN toDayOfWeek(toDate(date)) IN (6, 7) THEN 1
        ELSE 0
    END AS is_weekend,

    -- Metadata
    now() AS updated_at

FROM daily_breakdown
ORDER BY date DESC
