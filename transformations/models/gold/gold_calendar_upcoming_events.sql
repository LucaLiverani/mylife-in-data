-- Next 8 events. Handler reads {title, category, time, durationMinutes}.
-- Relative time ("in 2h") is rendered client-side from `time`, so it stays
-- fresh between dbt builds and compact on mobile.

{{ config(materialized='view', schema='gold') }}

SELECT
    title                                                    AS title,
    category                                                 AS category,
    -- ISO-8601 UTC ('…Z') so the browser's `new Date()` parses it as UTC,
    -- not local. NB: ClickHouse %i is minutes; %M is the month NAME.
    formatDateTime(started_at, '%Y-%m-%dT%H:%i:%SZ', 'UTC')  AS time,
    duration_minutes                                         AS durationMinutes
FROM {{ ref('silver_calendar_events') }}
-- Real upcoming plans only: exclude all-day holiday/birthday subscriptions,
-- which would otherwise fill "what's next" with the next public holiday.
WHERE started_at >= now() AND is_all_day = 0
ORDER BY started_at
LIMIT 8
