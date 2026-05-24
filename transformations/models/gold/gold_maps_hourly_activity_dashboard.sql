-- Hour-of-day activity histogram.

{{ config(materialized='view', schema='gold') }}

WITH hours AS (
    SELECT number AS h FROM numbers(24)
),
counts AS (
    SELECT hour_of_day AS h, count() AS activities
    FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0
    GROUP BY hour_of_day
)
SELECT
    toString(hours.h)                                AS hour,
    coalesce(counts.activities, toUInt64(0))         AS activities
FROM hours
LEFT JOIN counts USING (h)
ORDER BY hours.h
