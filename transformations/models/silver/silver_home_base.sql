-- Inferred home base: the locality you're most active in, weighted toward
-- directions (which signal physical presence, not just interest). One row.
--
-- v1 is a single anchor — the activity history is Zurich-dominated so this is
-- accurate. A time-varying home (rolling window, for relocations) is a future
-- refinement; trip detection only needs "where is home" to mark away-days.

{{ config(materialized='view', schema='silver') }}

WITH loc AS (
    SELECT
        locality,
        country,
        avg(lat) AS lat,
        avg(lng) AS lng,
        countIf(activity_type = 'directions') * 3
          + countIf(activity_type = 'view_place')
          + countIf(activity_type = 'search') AS weight
    FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0 AND locality != '' AND match_confidence >= 0.4
    GROUP BY locality, country
)
SELECT
    locality AS home_locality,
    country  AS home_country,
    lat      AS home_lat,
    lng      AS home_lng
FROM loc
ORDER BY weight DESC
LIMIT 1
