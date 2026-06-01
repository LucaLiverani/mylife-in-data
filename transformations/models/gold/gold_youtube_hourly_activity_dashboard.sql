-- Hour-of-day histogram. 24 rows.

{{ config(materialized='view', schema='gold') }}

WITH hours AS (
    SELECT number AS h FROM numbers(24)
),
per_hour AS (
    SELECT watched_hour AS h, count() AS activities
    FROM {{ ref('silver_youtube_watches') }}
    WHERE watched_date >= toDate('{{ var("kpi_start_date") }}')
    GROUP BY watched_hour
)
SELECT
    toString(hours.h)                                  AS hour,
    coalesce(per_hour.activities, toUInt64(0))         AS activities
FROM hours
LEFT JOIN per_hour USING (h)
ORDER BY hours.h
