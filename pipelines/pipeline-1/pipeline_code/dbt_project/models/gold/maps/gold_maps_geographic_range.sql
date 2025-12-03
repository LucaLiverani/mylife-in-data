{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Geographic Range & Travel Distance

    Analyzes geographic patterns and travel behavior.
    Includes:
    - Home base estimation
    - Travel radius and range
    - Distance metrics
    - Geographic clustering
    - Exploration patterns
*/

WITH locations_with_coords AS (
    SELECT
        activity_id,
        activity_time,
        activity_date,
        location_name,
        latitude,
        longitude,
        year,
        month,
        week_start
    FROM {{ ref('silver_google_maps_activities') }}
    WHERE
        latitude IS NOT NULL
        AND longitude IS NOT NULL
),

-- Estimate home base as the most frequently visited location
home_base AS (
    SELECT
        location_name AS home_location_name,
        latitude AS home_latitude,
        longitude AS home_longitude,
        COUNT(*) AS visit_count
    FROM locations_with_coords
    GROUP BY location_name, latitude, longitude
    ORDER BY visit_count DESC
    LIMIT 1
),

-- Calculate distances from home base
distances_from_home AS (
    SELECT
        l.activity_id,
        l.activity_time,
        l.activity_date,
        l.location_name,
        l.latitude,
        l.longitude,
        l.year,
        l.month,
        l.week_start,
        h.home_location_name,
        h.home_latitude,
        h.home_longitude,

        -- Distance from home in kilometers
        ROUND(
            geoDistance(l.longitude, l.latitude, h.home_longitude, h.home_latitude) / 1000,
            2
        ) AS distance_from_home_km

    FROM locations_with_coords l
    CROSS JOIN home_base h
),

-- Calculate pairwise distances between consecutive activities
activity_distances AS (
    SELECT
        activity_id,
        activity_time,
        activity_date,
        location_name,
        latitude,
        longitude,
        distance_from_home_km,
        year,
        month,
        week_start,

        -- Get previous location
        lagInFrame(latitude, 1) OVER (ORDER BY activity_time) AS prev_latitude,
        lagInFrame(longitude, 1) OVER (ORDER BY activity_time) AS prev_longitude,
        lagInFrame(activity_time, 1) OVER (ORDER BY activity_time) AS prev_activity_time,

        -- Calculate distance traveled from previous activity
        CASE
            WHEN lagInFrame(latitude, 1) OVER (ORDER BY activity_time) IS NOT NULL
            THEN ROUND(
                geoDistance(
                    longitude,
                    latitude,
                    lagInFrame(longitude, 1) OVER (ORDER BY activity_time),
                    lagInFrame(latitude, 1) OVER (ORDER BY activity_time)
                ) / 1000,
                2
            )
            ELSE 0
        END AS distance_traveled_km

    FROM distances_from_home
),

-- Aggregate by time periods
geographic_summary AS (
    SELECT
        activity_date,
        year,
        month,
        week_start,

        -- Daily metrics
        COUNT(*) AS daily_activities,
        COUNT(DISTINCT location_name) AS daily_unique_locations,

        -- Distance metrics
        ROUND(AVG(distance_from_home_km), 2) AS avg_distance_from_home_km,
        ROUND(MAX(distance_from_home_km), 2) AS max_distance_from_home_km,
        ROUND(MIN(distance_from_home_km), 2) AS min_distance_from_home_km,
        ROUND(SUM(distance_traveled_km), 2) AS total_distance_traveled_km,
        ROUND(AVG(distance_traveled_km), 2) AS avg_distance_traveled_km,

        -- Geographic spread (using standard deviation of coordinates)
        ROUND(stddevPop(latitude), 6) AS latitude_stddev,
        ROUND(stddevPop(longitude), 6) AS longitude_stddev,

        -- Bounding box
        MIN(latitude) AS min_latitude,
        MAX(latitude) AS max_latitude,
        MIN(longitude) AS min_longitude,
        MAX(longitude) AS max_longitude,

        -- Center point
        ROUND(AVG(latitude), 6) AS center_latitude,
        ROUND(AVG(longitude), 6) AS center_longitude

    FROM activity_distances
    GROUP BY activity_date, year, month, week_start
)

SELECT
    activity_date,
    year,
    month,
    week_start,

    -- Activity counts
    daily_activities,
    daily_unique_locations,

    -- Distance metrics
    avg_distance_from_home_km,
    max_distance_from_home_km,
    min_distance_from_home_km,
    total_distance_traveled_km,
    avg_distance_traveled_km,

    -- Geographic spread metrics
    latitude_stddev,
    longitude_stddev,

    -- Calculate approximate area covered (in square km) using bounding box
    ROUND(
        abs(
            geoDistance(min_longitude, min_latitude, max_longitude, min_latitude) *
            geoDistance(min_longitude, min_latitude, min_longitude, max_latitude)
        ) / 1000000,
        2
    ) AS approx_area_covered_sq_km,

    -- Bounding box coordinates
    min_latitude,
    max_latitude,
    min_longitude,
    max_longitude,
    center_latitude,
    center_longitude,

    -- Movement classification
    CASE
        WHEN max_distance_from_home_km >= 100 THEN 'Long Distance Travel'
        WHEN max_distance_from_home_km >= 50 THEN 'Regional Travel'
        WHEN max_distance_from_home_km >= 20 THEN 'Extended Local'
        WHEN max_distance_from_home_km >= 10 THEN 'Local Area'
        ELSE 'Immediate Vicinity'
    END AS travel_range_category,

    -- Exploration score (unique locations / total activities)
    ROUND(
        daily_unique_locations::Float64 / daily_activities,
        2
    ) AS exploration_score,

    -- Monthly aggregates
    SUM(total_distance_traveled_km) OVER (PARTITION BY year, month) AS monthly_total_distance_km,
    AVG(max_distance_from_home_km) OVER (PARTITION BY year, month) AS monthly_avg_max_distance_km,
    SUM(daily_unique_locations) OVER (PARTITION BY year, month) AS monthly_unique_locations

FROM geographic_summary
ORDER BY activity_date DESC
