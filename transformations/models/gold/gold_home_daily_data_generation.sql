-- Per-day cross-source event counts, last 90 days.
-- Handler names the calendar column `google` (legacy alias) — keep it.

{{ config(materialized='view', schema='gold') }}

SELECT
    toDate(event_ts)                                            AS date,
    countIf(source = 'spotify')                                 AS spotify,
    countIf(source = 'youtube')                                 AS youtube,
    countIf(source = 'calendar')                                AS google,
    countIf(source = 'maps')                                    AS maps
FROM {{ ref('silver_events_unified') }}
WHERE event_ts >= today() - 90
GROUP BY date
ORDER BY date
