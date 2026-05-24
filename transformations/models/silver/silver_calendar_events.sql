-- Cleaned-up Calendar events with derived `category` (alias-aware), date,
-- hour-of-day, duration_minutes, weekend flag.

{{ config(materialized='view', schema='silver') }}

WITH events AS (
    SELECT * FROM {{ source('bronze', 'calendar_events') }} FINAL
    WHERE status != 'cancelled'
),
aliases AS (
    SELECT calendar_name, display_category FROM silver.calendar_category_aliases FINAL
)
SELECT
    e.event_id                                                                  AS event_id,
    e.calendar_id                                                               AS calendar_id,
    e.calendar_name                                                             AS calendar_name,
    coalesce(a.display_category, e.calendar_name)                               AS category,
    e.started_at                                                                AS started_at,
    e.ended_at                                                                  AS ended_at,
    e.title                                                                     AS title,
    e.description                                                               AS description,
    e.location                                                                  AS location,
    e.status                                                                    AS status,
    e.attendee_count                                                            AS attendee_count,
    e.recurrence_id                                                             AS recurrence_id,
    toDate(e.started_at)                                                        AS event_date,
    toHour(e.started_at)                                                        AS hour_of_day,
    dateDiff('minute', e.started_at, e.ended_at)                                AS duration_minutes,
    toDayOfWeek(e.started_at)                                                   AS day_of_week,
    toUInt8(toDayOfWeek(e.started_at) IN (6,7))                                 AS is_weekend
FROM events e
LEFT JOIN aliases a USING (calendar_name)
