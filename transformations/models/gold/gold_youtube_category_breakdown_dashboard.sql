-- Category split (% of count + % of time + unique channels).
-- category_id is resolved to a name via a static mapping in the enricher;
-- here we just expose it. The frontend can resolve the name if needed.

{{ config(materialized='view', schema='gold') }}

WITH watches AS (
    SELECT * FROM {{ ref('silver_youtube_watches') }}
),
totals AS (
    SELECT
        count()                                                  AS total_count,
        sum(duration_seconds)                                    AS total_time
    FROM watches
)
SELECT
    category_id                                                  AS category_name,
    count()                                                      AS watch_count,
    sum(duration_seconds)                                        AS total_watch_time_seconds,
    formatReadableTimeDelta(sum(duration_seconds))               AS total_watch_time_formatted,
    round(count() / nullIf((SELECT total_count FROM totals), 0) * 100.0, 1) AS watch_percentage,
    round(
        sum(duration_seconds) / nullIf((SELECT total_time FROM totals), 0) * 100.0,
        1
    )                                                            AS time_percentage,
    uniqExact(channel_id)                                        AS unique_channels
FROM watches
WHERE category_id != ''
GROUP BY category_id
ORDER BY watch_count DESC
