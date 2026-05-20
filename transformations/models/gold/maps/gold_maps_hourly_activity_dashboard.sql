{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Hourly Activity Dashboard View

    Pre-aggregated hourly activity data optimized for dashboard consumption.
    Groups all activities by hour across all days of the week.

    Dashboard Use:
    - Simple SELECT * query
    - Hour formatted as readable string (e.g., "14:00")
    - Total activities summed across all days
*/

SELECT
    -- Pre-formatted hour string
    concat(toString(activity_hour), ':00') AS hour,

    -- Sum activities across all days for this hour
    sum(activity_count) AS activities,

    -- Keep activity_hour for ordering
    activity_hour

FROM {{ ref('gold_maps_hourly_heatmap') }}
GROUP BY activity_hour
ORDER BY activity_hour
