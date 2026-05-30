-- Per-day location timeline: the dominant locality each day, weighted toward
-- directions (physical presence) over searches/views (interest). Feeds trip
-- segmentation (Phase 4) — consecutive away-days cluster into trips.
--
-- `away` requires a directions signal that day, so a day spent searching
-- "flights to Bali" from home does NOT count as being in Bali. Days with no
-- confident geolocated activity are simply absent (no presence signal).

{{ config(materialized='view', schema='silver') }}

WITH day_loc AS (
    SELECT
        event_date,
        locality,
        country,
        avg(lat) AS lat,
        avg(lng) AS lng,
        count() AS n,
        countIf(activity_type = 'directions') * 3
          + countIf(activity_type = 'view_place')
          + countIf(activity_type = 'search') AS weight,
        countIf(activity_type = 'directions') AS directions
    FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0 AND locality != '' AND match_confidence >= 0.4
    GROUP BY event_date, locality, country
),
day_primary AS (
    SELECT
        event_date,
        argMax(locality, weight) AS locality,
        argMax(country, weight)  AS country,
        argMax(lat, weight)      AS lat,
        argMax(lng, weight)      AS lng,
        sum(n)                   AS activity_count,
        sum(directions)          AS directions_count
    FROM day_loc
    GROUP BY event_date
)
SELECT
    p.event_date                                                          AS event_date,
    p.locality                                                            AS locality,
    p.country                                                             AS country,
    p.lat                                                                 AS lat,
    p.lng                                                                 AS lng,
    p.activity_count                                                      AS activity_count,
    p.directions_count                                                    AS directions_count,
    h.home_locality                                                       AS home_locality,
    h.home_country                                                        AS home_country,
    round(greatCircleDistance(p.lng, p.lat, h.home_lng, h.home_lat) / 1000.0, 1) AS km_from_home,
    -- Away = physically elsewhere that day: a different country, or >50km from
    -- home in the same country. Presence-based (NOT directions-gated) so a
    -- multi-day trip isn't pocked with false "home" days when you didn't open
    -- Maps to navigate. Phantom search-only runs (a foreign place dominating a
    -- day's searches from your couch) are filtered at the TRIP level — a real
    -- trip must contain >=1 directions day (see trip_segmentation.py).
    multiIf(
        p.country != h.home_country,                                         1,
        p.locality != h.home_locality
            AND greatCircleDistance(p.lng, p.lat, h.home_lng, h.home_lat) > 50000, 1,
        0
    )                                                                     AS away
FROM day_primary p
CROSS JOIN {{ ref('silver_home_base') }} h
ORDER BY p.event_date
