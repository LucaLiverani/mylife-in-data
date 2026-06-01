-- Per-day event count feeding two Google-page charts off one array:
-- the "Daily events · last 30 days" line (slice(-30)) and the
-- "Activity · last 12 months" heatmap (weeks=53). Window spans 53 weeks (371d)
-- so the heatmap fills; the line chart slices its tail.
-- Counts all-day events too (trips, birthdays, OOO) — they're activity, and the
-- old is_all_day=0 + 90-day window left the 12-month heatmap ~80% empty.

{{ config(materialized='view', schema='gold') }}

SELECT
    event_date                                         AS date,
    count()                                            AS events
FROM {{ ref('silver_calendar_events') }}
WHERE event_date >= today() - 371 AND event_date <= today()
GROUP BY event_date
ORDER BY event_date
