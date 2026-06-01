-- {name, value, percentage} for the category-breakdown chart.

{{ config(materialized='view', schema='gold') }}

-- Since the shared kpi_start_date, no future rows (subscribed holidays run to 2031).
-- Includes all-day events so "Holidays" shows as a category; category labels
-- are already privacy-safe (email → "Personal") in the silver model.
WITH base AS (
    SELECT category
    FROM {{ ref('silver_calendar_events') }}
    WHERE started_at <= now() AND event_date >= toDate('{{ var("kpi_start_date") }}')
),
totals AS (
    SELECT count() AS total FROM base
)
SELECT
    category                                                AS name,
    count()                                                 AS value,
    coalesce(round(
        count() / nullIf((SELECT total FROM totals), 0) * 100.0,
        0
    ), 0)                                                   AS percentage
FROM base
GROUP BY category
ORDER BY value DESC
