-- {name, value, percentage} for the category-breakdown chart.

{{ config(materialized='view', schema='gold') }}

WITH totals AS (
    SELECT count() AS total FROM {{ ref('silver_calendar_events') }}
)
SELECT
    category                                                AS name,
    count()                                                 AS value,
    round(
        count() / nullIf((SELECT total FROM totals), 0) * 100.0,
        0
    )                                                       AS percentage
FROM {{ ref('silver_calendar_events') }}
GROUP BY category
ORDER BY value DESC
