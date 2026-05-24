-- 7×24 day×hour intensity, intensity = avg-per-week count / 5 (capped at 1).

{{ config(materialized='view', schema='gold') }}

WITH days AS (
    SELECT toInt16(number) AS dow FROM numbers(7)
),
hours AS (
    SELECT toInt16(number) AS hour FROM numbers(24)
),
slots AS (
    SELECT dow, hour FROM days CROSS JOIN hours
),
counts AS (
    SELECT
        toInt16(toDayOfWeek(started_at) - 1)       AS dow,
        toInt16(toHour(started_at))                AS hour,
        count()                                    AS c
    FROM {{ ref('silver_calendar_events') }}
    GROUP BY dow, hour
)
SELECT
    slots.dow                                                       AS day,
    slots.hour                                                      AS hour,
    least(round(coalesce(counts.c, 0) / 5.0, 2), toFloat64(1.0))    AS intensity
FROM slots
LEFT JOIN counts USING (dow, hour)
ORDER BY slots.dow, slots.hour
