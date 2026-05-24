-- Next 8 events. Handler reads {title, category, time, relativeTime, durationMinutes}.

{{ config(materialized='view', schema='gold') }}

SELECT
    title                                                                AS title,
    category                                                             AS category,
    started_at                                                           AS time,
    formatReadableTimeDelta(toUnixTimestamp(started_at) - toUnixTimestamp(now())) AS relativeTime,
    duration_minutes                                                     AS durationMinutes
FROM {{ ref('silver_calendar_events') }}
WHERE started_at >= now()
ORDER BY started_at
LIMIT 8
