-- Per-day event count, last 90 days.

{{ config(materialized='view', schema='gold') }}

SELECT
    event_date                                         AS date,
    count()                                            AS events
FROM {{ ref('silver_calendar_events') }}
WHERE event_date >= today() - 90
GROUP BY event_date
ORDER BY event_date
