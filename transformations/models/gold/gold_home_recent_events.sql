-- Top 10 events per source. Handler partitions by source on the way out
-- (spotify[]/youtube[]/maps[]). Relative-time and time-of-day labels are
-- rendered client-side from `time`, so no formatReadableTimeDelta here.

{{ config(materialized='view', schema='gold') }}

SELECT
    source                                                        AS source,
    row_number() OVER (PARTITION BY source ORDER BY event_ts DESC) AS recency_rank,
    title,
    multiIf(
        source = 'spotify',  subtitle,
        source = 'maps',     kind,
        ''
    )                                                             AS subtitle,
    -- ISO-8601 UTC ('…Z') so the browser's `new Date()` parses it as UTC,
    -- not local. NB: ClickHouse %i is minutes; %M is the month NAME.
    formatDateTime(event_ts, '%Y-%m-%dT%H:%i:%SZ', 'UTC')         AS time,
    image_url,
    kind                                                          AS activity_type,
    is_from_ads
FROM {{ ref('silver_events_unified') }}
QUALIFY recency_rank <= 10
