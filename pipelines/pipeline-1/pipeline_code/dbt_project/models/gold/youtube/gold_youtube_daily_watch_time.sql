{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Watch Activity

    Daily aggregated watch activity for time series charts.
    Note: Actual watch duration is not available in Google Takeout data,
    so we count videos watched per day as a proxy metric.

    Dashboard Use:
    - Daily activity trend chart
    - Time series analysis
*/

WITH daily_watches AS (
    SELECT
        activity_date AS date,
        COUNT(*) AS videos_watched,
        COUNT(DISTINCT video_id) AS unique_videos,
        countIf(activity_type = 'watched') AS watched_count,
        countIf(activity_type = 'search') AS search_count,
        countIf(is_from_ads = 1) AS ad_views_count,
        COUNT(DISTINCT
            CASE
                WHEN activity_hour >= 5 AND activity_hour < 12 THEN 'morning'
                WHEN activity_hour >= 12 AND activity_hour < 17 THEN 'afternoon'
                WHEN activity_hour >= 17 AND activity_hour < 21 THEN 'evening'
                ELSE 'night'
            END
        ) AS time_periods_active
    FROM {{ ref('silver_youtube_watch_history') }}
    GROUP BY activity_date
),

with_moving_avg AS (
    SELECT
        date,
        videos_watched,
        unique_videos,
        watched_count,
        search_count,
        ad_views_count,
        time_periods_active,

        -- 7-day moving average
        ROUND(
            AVG(videos_watched) OVER (
                ORDER BY date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS videos_7day_avg,

        -- 30-day moving average
        ROUND(
            AVG(videos_watched) OVER (
                ORDER BY date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS videos_30day_avg,

        toDayOfWeek(date) AS day_of_week,
        toStartOfWeek(date) AS week_start,
        toStartOfMonth(date) AS month_start

    FROM daily_watches
)

SELECT
    toString(date) AS date,
    videos_watched,
    unique_videos,
    watched_count,
    search_count,
    ad_views_count,
    time_periods_active,
    videos_7day_avg,
    videos_30day_avg,
    day_of_week,
    week_start,
    month_start,
    now() AS updated_at

FROM with_moving_avg
ORDER BY date DESC
