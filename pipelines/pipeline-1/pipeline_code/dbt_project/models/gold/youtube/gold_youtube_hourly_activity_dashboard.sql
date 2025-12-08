{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Hourly Activity Dashboard View

    Pre-formatted view of hourly activity for dashboard consumption.
    Hour formatted as readable string.

    Dashboard Use:
    - Simple SELECT * query
    - Hour formatted as string (e.g., "14:00")
*/

SELECT
    hour,
    total_activities AS activities,
    watched_count,
    time_of_day_label

FROM {{ ref('gold_youtube_hourly_activity') }}
ORDER BY activity_hour
