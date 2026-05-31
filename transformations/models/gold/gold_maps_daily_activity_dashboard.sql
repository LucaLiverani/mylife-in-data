-- Per-day activity split: directions, searches, explorations, other.
-- Last 30 days, oldest → newest, so the dashboard x-axis reads left-to-right
-- with the most recent day on the right. Mirrors
-- gold_youtube_daily_watch_time_breakdown_dashboard (today()-29 .. today(), ASC).

{{ config(materialized='view', schema='gold') }}

WITH per_day AS (
    SELECT
        event_date                                       AS date,
        countIf(activity_type = 'directions')            AS directions,
        countIf(activity_type = 'search')                AS searches,
        countIf(activity_type = 'view_place')            AS explorations,
        countIf(activity_type NOT IN ('directions','search','view_place')) AS other
    FROM {{ ref('silver_maps_activity_enriched') }}
    WHERE is_private = 0
      AND event_date >= today() - 29
      AND event_date <= today()
    GROUP BY event_date
)
SELECT date, directions, searches, explorations, other
FROM per_day
ORDER BY date
