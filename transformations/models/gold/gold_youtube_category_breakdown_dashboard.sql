-- Category split (% of count + % of time + unique channels).
-- category_id (YouTube Data API v3 videoCategories) is resolved to a display
-- name here via transform() so the dashboard pie shows "Education" not "27".
-- Mapping mirrors YOUTUBE_CATEGORY_NAMES in ingestion/google/youtube/enricher.py.
-- Empty until the enricher fills category_id (was: showed raw numeric ids).

{{ config(materialized='view', schema='gold') }}

WITH watches AS (
    SELECT * FROM {{ ref('silver_youtube_watches') }}
    WHERE watched_date >= toDate('{{ var("kpi_start_date") }}')
),
mapped AS (
    SELECT
        {{ youtube_category_name('category_id') }}               AS category_name,
        duration_seconds,
        channel_id
    FROM watches
    WHERE category_id != ''
),
totals AS (
    SELECT count() AS total_count, sum(duration_seconds) AS total_time FROM mapped
)
SELECT
    category_name                                                AS category_name,
    count()                                                      AS watch_count,
    sum(duration_seconds)                                        AS total_watch_time_seconds,
    formatReadableTimeDelta(sum(duration_seconds))               AS total_watch_time_formatted,
    round(count() / nullIf((SELECT total_count FROM totals), 0) * 100.0, 1) AS watch_percentage,
    round(
        sum(duration_seconds) / nullIf((SELECT total_time FROM totals), 0) * 100.0,
        1
    )                                                            AS time_percentage,
    uniqExact(channel_id)                                        AS unique_channels
FROM mapped
GROUP BY category_name
ORDER BY watch_count DESC
