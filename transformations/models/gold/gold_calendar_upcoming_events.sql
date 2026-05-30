-- Next 8 events. Handler reads {title, category, time, relativeTime, durationMinutes}.

{{ config(materialized='view', schema='gold') }}

SELECT
    title                                                                AS title,
    category                                                             AS category,
    started_at                                                           AS time,
    formatReadableTimeDelta(toUnixTimestamp(started_at) - toUnixTimestamp(now())) AS relativeTime,
    duration_minutes                                                     AS durationMinutes
FROM {{ ref('silver_calendar_events') }}
-- Real upcoming plans only: exclude all-day holiday/birthday subscriptions,
-- which would otherwise fill "what's next" with the next public holiday.
WHERE started_at >= now() AND is_all_day = 0
ORDER BY started_at
LIMIT 8
