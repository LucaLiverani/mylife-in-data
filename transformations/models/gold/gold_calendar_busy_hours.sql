-- 24 rows of {hour, events}.

{{ config(materialized='view', schema='gold') }}

WITH hours AS (
    SELECT number AS h FROM numbers(24)
),
counts AS (
    SELECT hour_of_day AS h, count() AS events
    FROM {{ ref('silver_calendar_events') }}
    WHERE is_all_day = 0 AND started_at <= now() AND event_date >= toDate('{{ var("kpi_start_date") }}')
    GROUP BY hour_of_day
)
SELECT
    concat(toString(hours.h), ':00')                  AS hour,
    coalesce(counts.events, toUInt64(0))              AS events
FROM hours
LEFT JOIN counts USING (h)
ORDER BY hours.h
