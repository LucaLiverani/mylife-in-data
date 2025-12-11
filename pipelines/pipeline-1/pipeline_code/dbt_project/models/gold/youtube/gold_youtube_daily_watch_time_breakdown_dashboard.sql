{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Dashboard View: Daily Watch Time Breakdown (Last 30 Days)

    Last 30 days of watch time breakdown for dashboard time series chart.
*/

SELECT
    date,
    watched_hours,
    searches_hours,
    visits_hours,
    ads_hours,
    other_hours,
    total_hours,
    watched_count,
    searches_count,
    visits_count,
    ads_count,
    day_name,
    is_weekend
FROM {{ ref('gold_youtube_daily_watch_time_breakdown') }}
WHERE date >= today() - INTERVAL 30 DAY
ORDER BY date ASC
