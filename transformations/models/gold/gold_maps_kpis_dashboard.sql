-- Travel KPIs for /api/travel/data, computed from activity (not Timeline).
-- Column list keeps the TravelKPIs shape the handler expects.
-- Privacy: only is_private=0 rows count toward public KPIs. Private events
-- are reported via gold_maps_private_summary (a single anonymized counter).

{{ config(materialized='view', schema='gold') }}

WITH a AS (
    SELECT * FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0
)
SELECT
    (SELECT count() FROM a)                                                       AS total_activities,
    (SELECT countIf(activity_type = 'directions') FROM a)                         AS total_directions,
    (SELECT countIf(activity_type = 'search') FROM a)                             AS total_searches,
    (SELECT countIf(activity_type = 'view_place') FROM a)                         AS total_explorations,
    (SELECT countIf(activity_type = 'view_place') FROM a)                         AS total_likely_visits,
    (SELECT uniqExact(event_date) FROM a)                                         AS days_with_activity,
    (SELECT uniqExact(place_name) FROM a WHERE place_name != '')                  AS unique_destinations,
    -- Cities/countries populate as maps_place_enrichment fills the catalog
    -- (locality/country). 0 until enrichment runs, then climbs.
    (SELECT uniqExactIf(locality, locality != '') FROM a)                         AS cities_visited,
    (SELECT uniqExactIf(country, country != '') FROM a)                           AS countries_visited,
    toString(coalesce((SELECT min(event_date) FROM a), toDate('1970-01-01')))     AS first_activity,
    toString(coalesce((SELECT max(event_date) FROM a), toDate('1970-01-01')))     AS last_activity,
    toInt32(coalesce((SELECT max(event_date) - min(event_date) FROM a), 0))       AS days_tracked,
    -- Per active day (uniqExact(event_date)) — meaningful even for a single
    -- day of data, and coalesced so the field is never NULL (a NULL here
    -- crashed travel/data.ts on `.toFixed()`).
    coalesce(round(
        (SELECT count() FROM a) /
        nullIf((SELECT uniqExact(event_date) FROM a), 0),
        1
    ), 0)                                                                         AS avg_activities_per_day,
    coalesce(round(
        (SELECT countIf(activity_type = 'directions') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    ), 0)                                                                         AS directions_pct,
    coalesce(round(
        (SELECT countIf(activity_type = 'search') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    ), 0)                                                                         AS search_pct,
    coalesce(round(
        (SELECT countIf(activity_type = 'view_place') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    ), 0)                                                                         AS explore_pct,
    -- Timeline-derived KPIs stay backed by silver.maps_trips (filled by
    -- monthly manual export). 0 until a Timeline import runs.
    (SELECT coalesce(sum(days), 0) FROM silver.maps_trips)                        AS days_away_from_home,
    (SELECT coalesce(max(days), 0) FROM silver.maps_trips)                        AS longest_trip_days,
    toInt32(0)                                                                    AS kilometers_traveled
