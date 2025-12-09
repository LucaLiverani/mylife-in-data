{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Activity Breakdown Dashboard View (Last 30 Days)

    Pre-filtered view showing activity type breakdown for the last 30 days.
    Optimized for multi-line time series charts.

    Dashboard Use:
    - Simple SELECT * query
    - Last 30 days only
    - All activity types as separate columns
*/

SELECT
    date,
    watched,
    searches,
    visits,
    subscriptions,
    likes,
    comments,
    shares,
    ads,
    other,
    total_activities,
    unique_videos,
    day_name,
    is_weekend

FROM {{ ref('gold_youtube_daily_activity_breakdown') }}
WHERE toDate(date) >= today() - 30
ORDER BY date ASC
