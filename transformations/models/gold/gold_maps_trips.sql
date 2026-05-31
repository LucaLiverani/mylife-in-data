-- Trip list for /api/travel/data — the merged source of truth for "real trips".
--
-- Layers three signals on the geometric candidates (silver.maps_trips):
--   * silver.maps_trips_enriched — the LLM verdict (is_trip, type, de-noised
--     destination, title, summary, confidence).
--   * silver.maps_trip_labels    — a human confirm / reject / edit override.
--   * silver.maps_trip_weather   — Open-Meteo historical weather for the window.
-- Precedence for the displayed fields is human edit > LLM > geometric, and a
-- row is shown only when it's a GENUINE trip: a human 'reject' hides it, a
-- 'confirm' forces it, otherwise the LLM verdict decides (un-enriched
-- candidates default to shown so new trips appear before the LLM has run).
--
-- silver.maps_trips* are DDL/Python tables (not dbt models), so they're
-- referenced by raw schema-qualified name; the trip_key join mirrors
-- trip_llm._trip_key exactly ('<started_at>_<ended_at>', ISO dates).

{{ config(materialized='view', schema='gold') }}

WITH trips AS (
    SELECT *, concat(toString(started_at), '_', toString(ended_at)) AS trip_key
    FROM silver.maps_trips
),
enriched AS (SELECT * FROM silver.maps_trips_enriched FINAL),
labels   AS (SELECT * FROM silver.maps_trip_labels   FINAL),
weather  AS (SELECT * FROM silver.maps_trip_weather  FINAL),
merged AS (
    SELECT
        m.trip_key                AS trip_key,
        m.started_at              AS started_at,
        m.ended_at                AS ended_at,
        m.days                    AS days,
        m.km                      AS km,
        m.destination             AS geo_destination,
        m.destination_country     AS geo_country,
        m.localities              AS localities,
        m.countries               AS countries,
        m.max_km                  AS max_km,
        -- join_use_nulls=0 → unmatched right rows carry type defaults, so an
        -- empty trip_key marks "no LLM verdict yet" (distinct from is_trip=0).
        toUInt8(e.trip_key != '') AS enriched_present,
        e.is_trip                 AS e_is_trip,
        e.confidence              AS e_confidence,
        e.trip_type               AS e_trip_type,
        e.title                   AS e_title,
        e.destination_label       AS e_destination,
        e.destination_country     AS e_country,
        e.summary                 AS e_summary,
        l.label                   AS label,
        l.edited_title            AS edited_title,
        l.edited_destination      AS edited_destination,
        l.edited_trip_type        AS edited_trip_type,
        w.temp_mean               AS temp_mean,
        w.precip_mm               AS precip_mm,
        w.summary                 AS weather
    FROM trips m
    LEFT JOIN enriched e ON e.trip_key = m.trip_key
    LEFT JOIN labels   l ON l.trip_key = m.trip_key
    LEFT JOIN weather  w ON w.trip_key = m.trip_key
)
SELECT
    toString(started_at)                                              AS start,
    toString(ended_at)                                               AS end,
    multiIf(edited_destination != '',                    edited_destination,
            enriched_present = 1 AND e_destination != '', e_destination,
            geo_destination)                                          AS destination,
    multiIf(edited_title != '',                  edited_title,
            enriched_present = 1 AND e_title != '', e_title,
            geo_destination)                                          AS title,
    multiIf(edited_trip_type != '',                  edited_trip_type,
            enriched_present = 1 AND e_trip_type != '', e_trip_type,
            '')                                                       AS trip_type,
    if(enriched_present = 1 AND e_country != '', e_country, geo_country) AS country,
    if(enriched_present = 1, e_summary, '')                           AS summary,
    if(enriched_present = 1, e_confidence, toFloat32(0))              AS confidence,
    days,
    km,
    localities,
    countries,
    max_km,
    round(temp_mean, 1)                                              AS temp_mean,
    round(precip_mm, 0)                                              AS precip_mm,
    weather,
    trip_key
FROM merged
-- Genuine-trip gate: human reject/confirm wins, else LLM verdict, else show.
WHERE multiIf(label = 'reject', 0, label = 'confirm', 1, enriched_present = 1, e_is_trip, 1) = 1
ORDER BY started_at DESC
