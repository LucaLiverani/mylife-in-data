-- Per-day activity split: directions, searches, explorations, other.
-- Handler keys: date, directions, searches, explorations, other.

{{ config(materialized='view', schema='gold') }}

WITH all_days AS (
    SELECT toDate(visit_date) AS date FROM {{ ref('silver_maps_visits') }}
    UNION DISTINCT
    SELECT toDate(searched_at) FROM {{ source('bronze', 'maps_search') }}
    UNION DISTINCT
    SELECT toDate(requested_at) FROM {{ source('bronze', 'maps_directions') }}
),
directions_per_day AS (
    SELECT toDate(requested_at) AS date, count() AS c
    FROM {{ source('bronze', 'maps_directions') }}
    GROUP BY date
),
search_per_day AS (
    SELECT toDate(searched_at) AS date, count() AS c
    FROM {{ source('bronze', 'maps_search') }}
    GROUP BY date
),
visits_per_day AS (
    SELECT visit_date AS date, count() AS c
    FROM {{ ref('silver_maps_visits') }}
    GROUP BY date
)
SELECT
    d.date                                  AS date,
    coalesce(dr.c, toUInt64(0))             AS directions,
    coalesce(sr.c, toUInt64(0))             AS searches,
    toUInt64(0)                             AS explorations,
    coalesce(vp.c, toUInt64(0))             AS other
FROM all_days d
LEFT JOIN directions_per_day dr USING (date)
LEFT JOIN search_per_day sr USING (date)
LEFT JOIN visits_per_day vp USING (date)
ORDER BY date DESC
LIMIT 90
