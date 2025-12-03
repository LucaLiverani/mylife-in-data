{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Maps Activity Summary

    Daily summary of Google Maps usage by activity type.
    Shows how you use Google Maps over time.

    Dashboard Use:
    - Time series of activity types
    - Activity type distribution pie/bar chart
    - Daily/monthly trends
*/

SELECT
    activity_date,

    -- Temporal dimensions
    toYear(activity_date) AS year,
    toMonth(activity_date) AS month,
    toStartOfWeek(activity_date) AS week_start,
    toDayOfWeek(activity_date) AS day_of_week,
    dateName('weekday', activity_date) AS day_name,

    -- Activity type counts
    countIf(activity_type = 'directions') AS directions_count,
    countIf(activity_type = 'search') AS search_count,
    countIf(activity_type = 'explore') AS explore_count,
    countIf(activity_type = 'place_view') AS place_view_count,
    countIf(activity_type = 'app_usage') AS app_usage_count,
    countIf(activity_type = 'custom_map') AS custom_map_count,

    -- Total activities
    count() AS total_activities,

    -- Visit metrics
    countIf(likely_visit = 1) AS likely_visits_count,
    round(countIf(likely_visit = 1) / count() * 100, 2) AS visit_percentage,

    -- Coordinate availability
    countIf(has_coordinates = 1) AS activities_with_coordinates,
    round(countIf(has_coordinates = 1) / count() * 100, 2) AS coordinate_coverage_pct,

    -- Unique locations
    uniq(location_name) AS unique_locations_viewed

FROM {{ ref('silver_google_maps_activities') }}
GROUP BY activity_date
ORDER BY activity_date DESC
