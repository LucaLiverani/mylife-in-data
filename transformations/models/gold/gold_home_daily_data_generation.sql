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
-- Upper bound excludes future-dated rows (e.g. subscribed-holiday calendar
-- events run years ahead) that otherwise appear as phantom points on the chart.
-- now64(3) (not now()) so the merged speed layer's still-playing track, stamped
-- at ms precision, isn't clipped by a second-precision bound.
WHERE event_ts >= today() - 90 AND event_ts <= now64(3)
GROUP BY date
ORDER BY date
