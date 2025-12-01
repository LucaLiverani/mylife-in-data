{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Activity Time Patterns

    Analyzes temporal patterns of location activities.
    Includes:
    - Hourly activity distribution
    - Day of week patterns
    - Monthly and seasonal trends
    - Peak activity times
    - Weekend vs weekday behavior
*/

WITH activity_counts AS (
    SELECT
        -- Temporal dimensions
        year,
        quarter,
        month,
        month_start,
        week_start,
        activity_date,
        day_of_week,
        day_name,
        activity_hour,
        time_of_day,
        is_weekend,

        -- Activity metrics
        COUNT(*) AS activity_count,
        COUNT(DISTINCT location_name) AS unique_locations,
        groupArray(location_name) AS locations

    FROM {{ ref('silver_google_maps_activities') }}
    GROUP BY
        year,
        quarter,
        month,
        month_start,
        week_start,
        activity_date,
        day_of_week,
        day_name,
        activity_hour,
        time_of_day,
        is_weekend
)

SELECT
    -- Date dimensions
    activity_date,
    year,
    quarter,
    month,
    month_start,
    week_start,
    day_of_week,
    day_name,
    is_weekend,

    -- Hour dimension
    activity_hour,
    time_of_day,

    -- Activity metrics
    SUM(activity_count) AS total_activities,
    SUM(unique_locations) AS unique_locations_visited,
    ROUND(AVG(activity_count), 2) AS avg_activities_per_location,

    -- Day-level aggregates
    SUM(SUM(activity_count)) OVER (PARTITION BY activity_date) AS daily_total_activities,
    SUM(SUM(unique_locations)) OVER (PARTITION BY activity_date) AS daily_unique_locations,

    -- Week-level aggregates
    SUM(SUM(activity_count)) OVER (PARTITION BY week_start) AS weekly_total_activities,

    -- Month-level aggregates
    SUM(SUM(activity_count)) OVER (PARTITION BY month_start) AS monthly_total_activities,

    -- Calculate percentile ranking within the day
    percent_rank() OVER (
        PARTITION BY activity_date
        ORDER BY SUM(activity_count)
    ) AS daily_activity_percentile

FROM activity_counts
GROUP BY
    activity_date,
    year,
    quarter,
    month,
    month_start,
    week_start,
    day_of_week,
    day_name,
    activity_hour,
    time_of_day,
    is_weekend
ORDER BY
    activity_date DESC,
    activity_hour
