{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Hourly Activity Heatmap

    Creates a heatmap-ready dataset showing activity intensity by hour and day of week.
    Perfect for visualization in dashboards to show:
    - Peak activity hours
    - Day of week patterns
    - Activity intensity over time
*/

WITH hourly_activity AS (
    SELECT
        day_of_week,
        day_name,
        activity_hour,
        time_of_day,
        is_weekend,
        COUNT(*) AS activity_count,
        COUNT(DISTINCT location_name) AS unique_locations,
        COUNT(DISTINCT activity_date) AS days_with_activity

    FROM {{ ref('silver_google_maps_activities') }}
    GROUP BY
        day_of_week,
        day_name,
        activity_hour,
        time_of_day,
        is_weekend
),

overall_stats AS (
    SELECT
        AVG(activity_count) AS avg_activity_count,
        stddevPop(activity_count) AS stddev_activity_count,
        MAX(activity_count) AS max_activity_count,
        MIN(activity_count) AS min_activity_count
    FROM hourly_activity
)

SELECT
    h.day_of_week,
    h.day_name,
    h.activity_hour,
    h.time_of_day,
    h.is_weekend,

    -- Activity metrics
    h.activity_count,
    h.unique_locations,
    h.days_with_activity,

    -- Average activities per day for this hour/day combination
    ROUND(h.activity_count::Float64 / h.days_with_activity, 2) AS avg_activities_per_occurrence,

    -- Normalized intensity score (0-100)
    CASE
        WHEN s.max_activity_count > s.min_activity_count
        THEN ROUND(
            ((h.activity_count - s.min_activity_count)::Float64 /
            (s.max_activity_count - s.min_activity_count)) * 100,
            1
        )
        ELSE 50.0
    END AS intensity_score,

    -- Z-score for statistical comparison
    CASE
        WHEN s.stddev_activity_count > 0
        THEN ROUND(
            (h.activity_count - s.avg_activity_count) / s.stddev_activity_count,
            2
        )
        ELSE 0.0
    END AS z_score,

    -- Classification
    CASE
        WHEN h.activity_count >= s.avg_activity_count + (2 * s.stddev_activity_count) THEN 'Very High'
        WHEN h.activity_count >= s.avg_activity_count + s.stddev_activity_count THEN 'High'
        WHEN h.activity_count >= s.avg_activity_count - s.stddev_activity_count THEN 'Medium'
        WHEN h.activity_count >= s.avg_activity_count - (2 * s.stddev_activity_count) THEN 'Low'
        ELSE 'Very Low'
    END AS intensity_category,

    -- Ranking within day of week
    dense_rank() OVER (
        PARTITION BY h.day_of_week
        ORDER BY h.activity_count DESC
    ) AS hour_rank_in_day,

    -- Ranking within hour across all days
    dense_rank() OVER (
        PARTITION BY h.activity_hour
        ORDER BY h.activity_count DESC
    ) AS day_rank_in_hour

FROM hourly_activity h
CROSS JOIN overall_stats s
ORDER BY
    h.day_of_week,
    h.activity_hour
