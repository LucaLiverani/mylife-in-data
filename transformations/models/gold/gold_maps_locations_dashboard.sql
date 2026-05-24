-- Top neighborhoods (was: per-place list). Aggregated to keep individual
-- visits out of the public dashboard.

{{ config(materialized='view', schema='gold') }}

SELECT
    multiIf(
        neighborhood != '' AND locality != '', concat(neighborhood, ', ', locality),
        locality != '',                        locality,
        country != '',                         country,
        'Unknown'
    )                                                                  AS name,
    avg(lat)                                                           AS lat,
    avg(lng)                                                           AS lng,
    formatReadableTimeDelta(count() * 60)                              AS duration,
    'aggregated'                                                       AS dwell_time_category,
    0.0                                                                AS distance_to_next_km
FROM {{ ref('silver_maps_activity_enriched') }}
WHERE is_private = 0
  AND lat != 0 AND lng != 0
GROUP BY name
ORDER BY count() DESC
LIMIT 500
