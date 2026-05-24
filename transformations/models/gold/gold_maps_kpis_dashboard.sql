-- Travel KPIs for /api/travel/data. Column list matches the TS handler's
-- TravelKPIs interface in dashboard/functions/api/travel/data.ts:10-26.

{{ config(materialized='view', schema='gold') }}

WITH visits AS (
    SELECT * FROM {{ ref('silver_maps_visits') }}
),
paths AS (
    SELECT * FROM {{ source('bronze', 'maps_path') }} FINAL
),
search AS (
    SELECT * FROM {{ source('bronze', 'maps_search') }} FINAL
),
directions AS (
    SELECT * FROM {{ source('bronze', 'maps_directions') }} FINAL
),
trips AS (
    SELECT * FROM silver.maps_trips
)
SELECT
    (SELECT count() FROM visits) + (SELECT count() FROM paths) + (SELECT count() FROM search) + (SELECT count() FROM directions)
                                                                                AS total_activities,
    (SELECT count() FROM directions)                                            AS total_directions,
    (SELECT count() FROM search)                                                AS total_searches,
    toUInt64(0)                                                                 AS total_explorations,
    (SELECT count() FROM visits)                                                AS total_likely_visits,
    (SELECT uniqExact(visit_date) FROM visits)                                  AS days_with_activity,
    (SELECT uniqExact(place_name) FROM visits WHERE place_name != '')           AS unique_destinations,
    toString((SELECT min(visit_date) FROM visits))                              AS first_activity,
    toString((SELECT max(visit_date) FROM visits))                              AS last_activity,
    (SELECT max(visit_date) - min(visit_date) FROM visits)                      AS days_tracked,
    round(
        (SELECT count() FROM visits) /
        nullIf((SELECT max(visit_date) - min(visit_date) FROM visits), 0),
        1
    )                                                                           AS avg_activities_per_day,
    0.0                                                                         AS directions_pct,
    0.0                                                                         AS search_pct,
    0.0                                                                         AS explore_pct,
    (SELECT sum(days) FROM trips)                                               AS days_away_from_home,
    (SELECT max(days) FROM trips)                                               AS longest_trip_days,
    round((SELECT sum(distance_m) FROM paths) / 1000.0, 0)                      AS kilometers_traveled
