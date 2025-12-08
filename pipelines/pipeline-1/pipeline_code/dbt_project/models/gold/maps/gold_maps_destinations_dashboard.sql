{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Top Destinations Dashboard View

    Pre-formatted view of gold_maps_top_destinations optimized for dashboard consumption.
    Column names match dashboard expectations.

    Dashboard Use:
    - Simple SELECT * with LIMIT
    - All columns renamed for dashboard
    - Pre-ordered by popularity
*/

SELECT
    -- Renamed columns for dashboard
    destination,
    request_count AS count,
    activity_type AS type,

    -- Keep original for ordering
    request_count AS request_count_raw

FROM {{ ref('gold_maps_top_destinations') }}
ORDER BY request_count DESC
