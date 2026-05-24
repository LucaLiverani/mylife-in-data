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
    toString(coalesce((SELECT min(event_date) FROM a), toDate('1970-01-01')))     AS first_activity,
    toString(coalesce((SELECT max(event_date) FROM a), toDate('1970-01-01')))     AS last_activity,
    toInt32(coalesce((SELECT max(event_date) - min(event_date) FROM a), 0))       AS days_tracked,
    round(
        (SELECT count() FROM a) /
        nullIf((SELECT max(event_date) - min(event_date) FROM a), 0),
        1
    )                                                                             AS avg_activities_per_day,
    round(
        (SELECT countIf(activity_type = 'directions') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    )                                                                             AS directions_pct,
    round(
        (SELECT countIf(activity_type = 'search') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    )                                                                             AS search_pct,
    round(
        (SELECT countIf(activity_type = 'view_place') FROM a) /
        nullIf((SELECT count() FROM a), 0) * 100.0,
        1
    )                                                                             AS explore_pct,
    -- Timeline-derived KPIs stay backed by silver.maps_trips (filled by
    -- monthly manual export). 0 until a Timeline import runs.
    (SELECT coalesce(sum(days), 0) FROM silver.maps_trips)                        AS days_away_from_home,
    (SELECT coalesce(max(days), 0) FROM silver.maps_trips)                        AS longest_trip_days,
    toInt32(0)                                                                    AS kilometers_traveled
