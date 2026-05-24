-- Per-day activity split: directions, searches, explorations, other.

{{ config(materialized='view', schema='gold') }}

WITH per_day AS (
    SELECT
        event_date                                       AS date,
        countIf(activity_type = 'directions')            AS directions,
        countIf(activity_type = 'search')                AS searches,
        countIf(activity_type = 'view_place')            AS explorations,
        countIf(activity_type NOT IN ('directions','search','view_place')) AS other
    FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0
    GROUP BY event_date
)
SELECT date, directions, searches, explorations, other
FROM per_day
ORDER BY date DESC
LIMIT 90
