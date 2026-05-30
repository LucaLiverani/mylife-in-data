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
    -- Category = alias if defined, else "Personal" for the owner's own calendar
    -- (calendar_name is an email — never surface it), else the subscription
    -- name (e.g. "Holidays in Switzerland"). LEFT JOIN misses give '' not NULL,
    -- so test for '' rather than coalesce.
    if(a.display_category != '', a.display_category,
       if(position(e.calendar_name, '@') > 0, 'Personal', e.calendar_name))     AS category,
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
    toUInt8(toDayOfWeek(e.started_at) IN (6,7))                                 AS is_weekend,
    -- All-day events (holidays, multi-day trips, birthdays) start at midnight
    -- and span whole days. They distort time-based KPIs (meeting hours, busy
    -- hours) so gold models exclude them; counts/categories still include them.
    toUInt8(
        toHour(e.started_at) = 0 AND toMinute(e.started_at) = 0
        AND dateDiff('minute', e.started_at, e.ended_at) >= 1440
        AND dateDiff('minute', e.started_at, e.ended_at) % 1440 = 0
    )                                                                           AS is_all_day
FROM events e
LEFT JOIN aliases a USING (calendar_name)
