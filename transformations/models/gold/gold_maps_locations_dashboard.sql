-- Top neighborhoods (was: per-place list). Aggregated to keep individual
-- visits out of the public dashboard.

{{ config(materialized='view', schema='gold') }}

-- Qualify the source-table references with `s.` so ClickHouse's name
-- resolver doesn't conflate the `lat`/`lng` SELECT aliases (which are
-- aggregates) with the same-named columns referenced in WHERE. Without
-- this, ClickHouse raises ILLEGAL_AGGREGATION: "Aggregate function
-- avg(lat) AS lat is found in WHERE in query."
SELECT
    multiIf(
        s.neighborhood != '' AND s.locality != '', concat(s.neighborhood, ', ', s.locality),
        s.locality != '',                          s.locality,
        s.country != '',                           s.country,
        'Unknown'
    )                                                                  AS name,
    avg(s.lat)                                                         AS lat,
    avg(s.lng)                                                         AS lng,
    formatReadableTimeDelta(count() * 60)                              AS duration,
    'aggregated'                                                       AS dwell_time_category,
    0.0                                                                AS distance_to_next_km
FROM {{ ref('silver_maps_activity_enriched') }} s
WHERE s.is_private = 0
  AND s.lat != 0 AND s.lng != 0
  AND s.match_confidence >= 0.4                                 -- drop low-confidence / junk geocodes
  AND s.match_type NOT IN ('country', 'state', 'unresolved')   -- too coarse to pin as a point
  -- Geographic gate: only countries with a directions activity (you navigated
  -- there). Removes the junk-country scatter — generic terms OSM resolves to
  -- villages in countries you've never been to (searches/views, zero directions).
  AND s.country IN (
      SELECT DISTINCT country FROM {{ ref('silver_maps_activity_enriched') }}
      WHERE is_private = 0 AND activity_type = 'directions' AND country != ''
  )
GROUP BY name
-- Corroboration: a real place is either navigated-to (directions) or engaged
-- with more than once. Drops lone mis-geocodes — a one-off generic search
-- ("Pizza", "Rosti") that OSM resolves to an obscure hamlet at confidence 1.0.
HAVING count() >= 2 OR countIf(s.activity_type = 'directions') > 0
ORDER BY count() DESC
LIMIT 500
