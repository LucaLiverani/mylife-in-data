{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Location Clusters & Geographic Areas

    Groups locations into geographic clusters to identify:
    - Neighborhood/area-based activity patterns
    - Geographic hotspots
    - Regional exploration
    - City/area visit frequency
*/

WITH locations AS (
    SELECT
        location_name,
        latitude,
        longitude,
        activity_date,
        activity_time,
        year,
        month
    FROM {{ ref('silver_google_maps_activities') }}
    WHERE
        latitude IS NOT NULL
        AND longitude IS NOT NULL
),

-- Create a simple grid-based clustering (0.01 degree ~ 1km)
location_grid AS (
    SELECT
        location_name,
        latitude,
        longitude,
        activity_date,
        activity_time,
        year,
        month,

        -- Grid cell assignment (for clustering nearby locations)
        FLOOR(latitude / 0.01) AS lat_grid,
        FLOOR(longitude / 0.01) AS lon_grid,

        -- Coarser grid for broader areas (0.05 degree ~ 5km)
        FLOOR(latitude / 0.05) AS lat_area_grid,
        FLOOR(longitude / 0.05) AS lon_area_grid

    FROM locations
),

-- Aggregate by grid cells (fine-grained clusters)
cluster_summary AS (
    SELECT
        lat_grid,
        lon_grid,

        -- Representative coordinates (center of cluster)
        ROUND(AVG(latitude), 6) AS cluster_center_lat,
        ROUND(AVG(longitude), 6) AS cluster_center_lon,

        -- Cluster metrics
        COUNT(*) AS total_visits,
        COUNT(DISTINCT location_name) AS unique_locations_in_cluster,
        COUNT(DISTINCT activity_date) AS unique_visit_days,

        -- Location info
        groupArray(DISTINCT location_name) AS locations_in_cluster,

        -- Temporal info
        MIN(activity_time) AS first_visit,
        MAX(activity_time) AS last_visit,
        COUNT(DISTINCT year) AS years_visited,
        COUNT(DISTINCT month) AS months_visited

    FROM location_grid
    GROUP BY lat_grid, lon_grid
),

-- Aggregate by broader areas
area_summary AS (
    SELECT
        lat_area_grid,
        lon_area_grid,

        -- Representative coordinates
        ROUND(AVG(latitude), 6) AS area_center_lat,
        ROUND(AVG(longitude), 6) AS area_center_lon,

        -- Area metrics
        COUNT(*) AS total_visits_in_area,
        COUNT(DISTINCT location_name) AS unique_locations_in_area,
        COUNT(DISTINCT activity_date) AS unique_visit_days_in_area,

        -- Temporal info
        MIN(activity_time) AS area_first_visit,
        MAX(activity_time) AS area_last_visit

    FROM location_grid
    GROUP BY lat_area_grid, lon_area_grid
),

-- Rank clusters by visit frequency
ranked_clusters AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY total_visits DESC) AS cluster_rank,
        dense_rank() OVER (ORDER BY total_visits DESC) AS cluster_dense_rank
    FROM cluster_summary
)

SELECT
    -- Cluster identification
    lat_grid,
    lon_grid,
    cluster_center_lat,
    cluster_center_lon,

    -- Create a readable cluster ID
    concat(
        'CLUSTER_',
        toString(lat_grid),
        '_',
        toString(lon_grid)
    ) AS cluster_id,

    -- Visit metrics
    total_visits,
    unique_locations_in_cluster,
    unique_visit_days,

    -- Location details
    locations_in_cluster,
    arrayStringConcat(locations_in_cluster, ' | ') AS locations_list,

    -- Temporal metrics
    first_visit,
    last_visit,
    dateDiff('day', first_visit, last_visit) AS days_span,
    years_visited,
    months_visited,

    -- Density metrics
    ROUND(total_visits::Float64 / unique_visit_days, 2) AS avg_visits_per_day,
    ROUND(unique_locations_in_cluster::Float64 / unique_visit_days, 2) AS avg_locations_per_day,

    -- Ranking
    cluster_rank,
    cluster_dense_rank,

    -- Classification
    CASE
        WHEN total_visits >= 100 THEN 'Major Hotspot'
        WHEN total_visits >= 50 THEN 'Frequent Area'
        WHEN total_visits >= 20 THEN 'Regular Area'
        WHEN total_visits >= 10 THEN 'Occasional Area'
        ELSE 'Rarely Visited'
    END AS cluster_category,

    -- Recency
    dateDiff('day', last_visit, now()) AS days_since_last_visit,
    CASE
        WHEN dateDiff('day', last_visit, now()) <= 30 THEN 'Recent'
        WHEN dateDiff('day', last_visit, now()) <= 90 THEN 'Somewhat Recent'
        WHEN dateDiff('day', last_visit, now()) <= 365 THEN 'Past Year'
        ELSE 'Historical'
    END AS recency_category

FROM ranked_clusters
ORDER BY total_visits DESC
