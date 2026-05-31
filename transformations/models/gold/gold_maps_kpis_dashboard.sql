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
    -- Cities/countries count only places you actually NAVIGATED in (a directions
    -- activity). Searches/views alone mis-geocode generic terms to far-flung
    -- villages; counting those inflated the totals to 929 cities / 106 countries.
    (SELECT count() FROM (
        SELECT locality FROM a WHERE locality != ''
        GROUP BY locality HAVING countIf(activity_type = 'directions') > 0
    ))                                                                            AS cities_visited,
    (SELECT count() FROM (
        SELECT country FROM a WHERE country != ''
        GROUP BY country HAVING countIf(activity_type = 'directions') > 0
    ))                                                                            AS countries_visited,
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
    -- Movement KPIs over GENUINE trips (gold_maps_trips already applies the
    -- LLM verdict + human overrides + genuine-trip gate), so the 2 rejected
    -- candidates don't inflate them. 0 until trips exist.
    (SELECT coalesce(sum(days), 0) FROM {{ ref('gold_maps_trips') }})             AS days_away_from_home,
    (SELECT coalesce(max(days), 0) FROM {{ ref('gold_maps_trips') }})             AS longest_trip_days,
    (SELECT coalesce(toInt32(sum(km)), 0) FROM {{ ref('gold_maps_trips') }})      AS kilometers_traveled,
    -- Distinct destinations whose FIRST trip is in the current year.
    (SELECT count() FROM (
        SELECT destination, min(toYear(toDate(start))) AS first_year
        FROM {{ ref('gold_maps_trips') }} GROUP BY destination
        HAVING first_year = toYear(today())
    ))                                                                            AS new_places_this_year,
    -- Inferred home base (for the dashboard's home-base strip). Read through
    -- this gold view so the Worker never SELECTs silver directly.
    coalesce((SELECT home_locality FROM silver.silver_home_base LIMIT 1), '')      AS home_locality,
    coalesce((SELECT home_country  FROM silver.silver_home_base LIMIT 1), '')      AS home_country
