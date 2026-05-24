-- Hour-of-day activity histogram for /api/travel/data.charts.hourlyActivity.

{{ config(materialized='view', schema='gold') }}

WITH hours AS (
    SELECT number AS h FROM numbers(24)
)
SELECT
    toString(h)                                AS hour,
    coalesce(activities_per_hour.activities, toUInt64(0)) AS activities
FROM hours
LEFT JOIN (
    SELECT
        toHour(started_at)                     AS h,
        count()                                AS activities
    FROM {{ ref('silver_maps_visits') }}
    GROUP BY h
) AS activities_per_hour USING (h)
ORDER BY h
