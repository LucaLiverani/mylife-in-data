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
    WHERE is_all_day = 0 AND started_at <= now() AND event_date >= toDate('{{ var("kpi_start_date") }}')
    GROUP BY dow, hour
),
-- Normalise intensity against the busiest slot so the heatmap spans 0..1
-- regardless of window length (the old /5.0 saturated over a full year).
maxc AS (
    SELECT max(c) AS m FROM counts
)
SELECT
    slots.dow                                                       AS day,
    slots.hour                                                      AS hour,
    coalesce(round(counts.c / nullIf((SELECT m FROM maxc), 0), 2), 0) AS intensity
FROM slots
LEFT JOIN counts USING (dow, hour)
ORDER BY slots.dow, slots.hour
