-- Per-day event count, last 90 days.

{{ config(materialized='view', schema='gold') }}

SELECT
    event_date                                         AS date,
    count()                                            AS events
FROM {{ ref('silver_calendar_events') }}
WHERE is_all_day = 0 AND event_date >= today() - 90 AND event_date <= today()
GROUP BY event_date
ORDER BY event_date
