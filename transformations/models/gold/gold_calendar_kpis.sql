-- /api/google/calendar.kpis — scheduled-time KPIs over the trailing 365 days.
--
-- Scope decisions (so the numbers mean something):
--   * Timed events only (is_all_day = 0). All-day holidays/trips would
--     otherwise inflate meetingHours into the tens of thousands and pin every
--     "busy hour" at 00:00.
--   * Trailing 365 days, no future rows. Subscribed-holiday calendars run out
--     to 2031; without a bound, freeDays counted ~16 years of span.
--   * plansCount = timed meetings with at least one other attendee.
--   * freeDays = days in the last year with no timed event on the calendar.

{{ config(materialized='view', schema='gold') }}

WITH ev AS (
    SELECT *
    FROM {{ ref('silver_calendar_events') }}
    WHERE is_all_day = 0
      AND started_at <= now()
      AND event_date >= today() - 365
),
days AS (
    SELECT event_date AS d, count() AS c FROM ev GROUP BY event_date
),
weekday_split AS (
    SELECT
        arrayElement(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], day_of_week) AS day,
        count() AS events
    FROM ev
    GROUP BY day_of_week
),
busiest AS (
    SELECT day FROM weekday_split ORDER BY events DESC LIMIT 1
)
SELECT
    (SELECT countIf(attendee_count > 0) FROM ev)                                AS plansCount,
    toUInt32(greatest(0, 365 - (SELECT count() FROM days)))                     AS freeDays,
    (SELECT count() FROM ev)                                                    AS totalEvents,
    toUInt32(round((SELECT sum(duration_minutes) FROM ev) / 60.0, 0))           AS meetingHours,
    coalesce(round(
        (SELECT count() FROM ev) / nullIf((SELECT count() FROM days), 0),
        1
    ), 0)                                                                       AS avgDaily,
    coalesce((SELECT day FROM busiest), 'Mon')                                  AS busiestDay
