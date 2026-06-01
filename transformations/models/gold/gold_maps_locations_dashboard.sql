-- Map points = neighbourhoods you NAVIGATED to (a directions signal = real
-- physical presence). Searches/views are excluded — they're interest, not
-- where you've been, and they mis-geocode generic terms to far places.
-- Aggregated to keep individual visits out of the public dashboard.

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
  AND s.event_date >= toDate('{{ var("kpi_start_date") }}')
  AND s.lat != 0 AND s.lng != 0
  AND s.match_confidence >= 0.4                                 -- drop low-confidence / junk geocodes
  AND s.match_type NOT IN ('country', 'state', 'unresolved')   -- too coarse to pin as a point
  -- Country geo-gate: only countries with a CORROBORATED trip (gold_maps_trips
  -- is LLM-validated + de-noised) or home. A handful of directions still
  -- mis-geocode their destination to far countries you've never been (London,
  -- India, the Philippines, the US, …); gating to real trip countries drops
  -- those, while KEEPING low-directions-but-real trips (Tunisia, Ecuador,
  -- Brazil) that a raw directions-count threshold would wrongly cut.
  AND s.country IN (
      SELECT home_country FROM {{ ref('silver_home_base') }}
      UNION DISTINCT
      SELECT country FROM {{ ref('gold_maps_trips') }} WHERE country != ''
  )
GROUP BY name
-- Presence-based: only places you NAVIGATED to (a directions hit) reach the
-- map — searches/views are interest, not where you've been.
HAVING countIf(s.activity_type = 'directions') > 0
ORDER BY countIf(s.activity_type = 'directions') DESC, count() DESC
LIMIT 500
