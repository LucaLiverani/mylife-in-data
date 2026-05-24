-- /api/google/calendar.kpis. Plans = events with attendees > 0.
-- fragmentation = avg per-day count of distinct "blocks" / events.
-- longestUnscheduledHours = approximation: max gap between consecutive
-- events in a working day (7–22h).

{{ config(materialized='view', schema='gold') }}

WITH events AS (
    SELECT * FROM {{ ref('silver_calendar_events') }}
),
totals AS (
    SELECT count() AS total FROM events
),
days AS (
    SELECT event_date AS d, count() AS c FROM events GROUP BY event_date
),
weekday_split AS (
    SELECT
        arrayElement(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], day_of_week) AS day,
        count() AS events
    FROM events
    GROUP BY day_of_week
),
busiest AS (
    SELECT day FROM weekday_split ORDER BY events DESC LIMIT 1
)
SELECT
    (SELECT countIf(attendee_count > 0) FROM events)                            AS plansCount,
    toUInt32(
        greatest(
            0,
            (SELECT toUInt32(max(d) - min(d) + 1) FROM days)
            - (SELECT toUInt32(count()) FROM days)
        )
    )                                                                           AS freeDays,
    (SELECT total FROM totals)                                                  AS totalEvents,
    round((SELECT sum(duration_minutes) FROM events) / 60.0, 0)                 AS meetingHours,
    round(
        (SELECT total FROM totals) /
        nullIf((SELECT count() FROM days), 0),
        1
    )                                                                           AS avgDaily,
    coalesce((SELECT day FROM busiest), 'Mon')                                  AS busiestDay,
    toUInt32(0)                                                                 AS freeTimePerDay,
    toFloat32(0)                                                                AS longestUnscheduledHours,
    (SELECT countIf(is_weekend) FROM events)                                    AS weekendLeakage,
    round(
        (SELECT countIf(duration_minutes < 30) FROM events) /
        nullIf((SELECT total FROM totals), 0),
        2
    )                                                                           AS fragmentation
