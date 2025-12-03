{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Location Timeline & Journey Patterns

    Creates a timeline of location activities with journey insights.
    Includes:
    - Sequential ordering of locations
    - Time spent at each location (estimated from next activity)
    - Distance traveled between locations
    - Journey patterns and routines
*/

WITH ordered_activities AS (
    SELECT
        activity_id,
        activity_time,
        activity_date,
        location_name,
        location_address,
        latitude,
        longitude,
        day_of_week,
        day_name,
        is_weekend,
        time_of_day,
        activity_hour,

        -- Get next activity details using window functions
        leadInFrame(activity_time) OVER (ORDER BY activity_time) AS next_activity_time,
        leadInFrame(location_name) OVER (ORDER BY activity_time) AS next_location_name,
        leadInFrame(latitude) OVER (ORDER BY activity_time) AS next_latitude,
        leadInFrame(longitude) OVER (ORDER BY activity_time) AS next_longitude,

        -- Get previous activity for context
        lagInFrame(location_name, 1) OVER (ORDER BY activity_time) AS prev_location_name,
        lagInFrame(activity_time, 1) OVER (ORDER BY activity_time) AS prev_activity_time

    FROM {{ ref('silver_google_maps_activities') }}
    WHERE
        latitude IS NOT NULL
        AND longitude IS NOT NULL
)

SELECT
    activity_id,
    activity_time,
    activity_date,
    location_name,
    location_address,
    latitude,
    longitude,
    day_of_week,
    day_name,
    is_weekend,
    time_of_day,
    activity_hour,

    -- Journey context
    prev_location_name,
    next_location_name,

    -- Time spent at location (minutes until next activity)
    CASE
        WHEN next_activity_time IS NOT NULL
        THEN dateDiff('minute', activity_time, next_activity_time)
        ELSE NULL
    END AS minutes_until_next_activity,

    -- Categorize dwell time
    CASE
        WHEN next_activity_time IS NULL THEN 'Unknown'
        WHEN dateDiff('minute', activity_time, next_activity_time) <= 15 THEN 'Quick Stop (0-15min)'
        WHEN dateDiff('minute', activity_time, next_activity_time) <= 60 THEN 'Short Visit (15-60min)'
        WHEN dateDiff('minute', activity_time, next_activity_time) <= 180 THEN 'Medium Stay (1-3h)'
        WHEN dateDiff('minute', activity_time, next_activity_time) <= 480 THEN 'Long Stay (3-8h)'
        ELSE 'Extended Stay (8h+)'
    END AS dwell_time_category,

    -- Distance to next location (in kilometers using Haversine formula)
    CASE
        WHEN next_latitude IS NOT NULL AND next_longitude IS NOT NULL
        THEN ROUND(
            geoDistance(longitude, latitude, next_longitude, next_latitude) / 1000,
            2
        )
        ELSE NULL
    END AS distance_to_next_km,

    -- Identify if moved to a different location
    CASE
        WHEN next_location_name IS NULL THEN 'Last Activity'
        WHEN location_name = next_location_name THEN 'Same Location'
        ELSE 'Different Location'
    END AS movement_type,

    -- Calculate speed (km/h) between locations
    CASE
        WHEN next_activity_time IS NOT NULL
            AND next_latitude IS NOT NULL
            AND next_longitude IS NOT NULL
            AND dateDiff('minute', activity_time, next_activity_time) > 0
        THEN ROUND(
            (geoDistance(longitude, latitude, next_longitude, next_latitude) / 1000) /
            (dateDiff('minute', activity_time, next_activity_time) / 60.0),
            1
        )
        ELSE NULL
    END AS avg_speed_kmh,

    -- Classify travel mode based on speed
    CASE
        WHEN next_activity_time IS NULL THEN NULL
        WHEN dateDiff('minute', activity_time, next_activity_time) > 480 THEN 'Stationary'
        WHEN (geoDistance(longitude, latitude, next_longitude, next_latitude) / 1000) /
             (dateDiff('minute', activity_time, next_activity_time) / 60.0) <= 6 THEN 'Walking'
        WHEN (geoDistance(longitude, latitude, next_longitude, next_latitude) / 1000) /
             (dateDiff('minute', activity_time, next_activity_time) / 60.0) <= 25 THEN 'Cycling'
        WHEN (geoDistance(longitude, latitude, next_longitude, next_latitude) / 1000) /
             (dateDiff('minute', activity_time, next_activity_time) / 60.0) <= 80 THEN 'Driving/Transit'
        ELSE 'Fast Transit'
    END AS estimated_travel_mode,

    -- Time since previous activity (in minutes)
    CASE
        WHEN prev_activity_time IS NOT NULL
        THEN dateDiff('minute', prev_activity_time, activity_time)
        ELSE NULL
    END AS minutes_since_prev_activity

FROM ordered_activities
ORDER BY activity_time DESC
