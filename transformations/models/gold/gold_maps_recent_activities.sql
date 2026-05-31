-- Last 10 Maps activities, aggregated by neighborhood (no per-address detail).
-- Handler keys: time, location, type, timeOfDay.

{{ config(materialized='view', schema='gold') }}

SELECT
    -- Emit ISO-8601 UTC ('…Z') so the browser's `new Date()` parses it as UTC,
    -- not local — otherwise "time ago" is off by the viewer's TZ offset.
    formatDateTime(event_ts, '%Y-%m-%dT%H:%M:%SZ', 'UTC')                     AS time,
    multiIf(
        neighborhood != '' AND locality != '', concat(neighborhood, ', ', locality),
        locality != '',                        locality,
        country != '',                         country,
        'Unknown'
    )                                                                         AS location,
    multiIf(
        activity_type = 'directions',                  'directions',
        activity_type = 'search' AND primary_type != '', concat('search · ', primary_type),
        activity_type = 'search',                      'search',
        primary_type != '',                            primary_type,
        'view'
    )                                                                         AS type,
    CASE
        WHEN hour_of_day < 12 THEN 'Morning'
        WHEN hour_of_day < 18 THEN 'Afternoon'
        ELSE 'Evening'
    END                                                                       AS timeOfDay
FROM {{ ref('silver_maps_activity_enriched') }}
WHERE is_private = 0
ORDER BY event_ts DESC
LIMIT 10
