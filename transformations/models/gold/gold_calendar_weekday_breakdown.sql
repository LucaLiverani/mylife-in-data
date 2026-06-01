-- [{day, events}] across the 7-day week.

{{ config(materialized='view', schema='gold') }}

WITH days AS (
    SELECT 1 AS dow, 'Mon' AS day UNION ALL
    SELECT 2, 'Tue' UNION ALL SELECT 3, 'Wed' UNION ALL SELECT 4, 'Thu' UNION ALL
    SELECT 5, 'Fri' UNION ALL SELECT 6, 'Sat' UNION ALL SELECT 7, 'Sun'
),
counts AS (
    SELECT day_of_week AS dow, count() AS events
    FROM {{ ref('silver_calendar_events') }}
    WHERE is_all_day = 0 AND started_at <= now() AND event_date >= toDate('{{ var("kpi_start_date") }}')
    GROUP BY day_of_week
)
SELECT
    days.day                                  AS day,
    coalesce(counts.events, toUInt64(0))      AS events
FROM days
LEFT JOIN counts USING (dow)
ORDER BY days.dow
