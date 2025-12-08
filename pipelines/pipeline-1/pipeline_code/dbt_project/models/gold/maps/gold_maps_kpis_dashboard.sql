{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Maps KPIs Dashboard View

    Pre-formatted view of gold_maps_kpis optimized for dashboard consumption.
    All fields are ready for direct display without further transformation.

    Dashboard Use:
    - Simple SELECT * query
    - All dates formatted as strings
    - All columns match dashboard expectations
*/

SELECT
    -- Activity counts
    total_activities,
    total_directions,
    total_searches,
    total_explorations,
    total_likely_visits,
    days_with_activity,
    unique_destinations,

    -- Temporal (formatted as strings)
    toString(first_activity) AS first_activity,
    toString(last_activity) AS last_activity,
    days_tracked,

    -- Averages
    avg_activities_per_day,

    -- Percentages
    directions_pct,
    search_pct,
    explore_pct

FROM {{ ref('gold_maps_kpis') }}
