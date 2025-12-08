{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Location Timeline Dashboard View

    Pre-formatted view of gold_maps_location_timeline optimized for dashboard map display.
    All fields are renamed and formatted for direct consumption.

    Dashboard Use:
    - Simple SELECT * with LIMIT
    - All coordinates validated (non-null)
    - Duration pre-formatted as readable string
    - Column names match dashboard expectations
*/

SELECT
    -- Renamed columns for dashboard
    location_name AS name,
    latitude AS lat,
    longitude AS lng,
    dwell_time_category,
    distance_to_next_km,

    -- Pre-computed duration string
    concat(
        toString(minutes_until_next_activity DIV 60), 'h ',
        toString(minutes_until_next_activity % 60), 'm'
    ) AS duration,

    -- Keep original timestamp for ordering
    activity_time

FROM {{ ref('gold_maps_location_timeline') }}
WHERE
    latitude IS NOT NULL
    AND longitude IS NOT NULL
    AND location_name IS NOT NULL
    AND location_name != ''
ORDER BY activity_time DESC
