-- Top 10 events per source. Handler partitions by source on the way out
-- (spotify[]/youtube[]/maps[]).

{{ config(materialized='view', schema='gold') }}

SELECT
    source                                                        AS source,
    row_number() OVER (PARTITION BY source ORDER BY event_ts DESC) AS recency_rank,
    title,
    multiIf(
        source = 'spotify',  subtitle,
        source = 'youtube',  formatReadableTimeDelta(toUnixTimestamp(now()) - toUnixTimestamp(event_ts)),
        source = 'maps',     kind,
        ''
    )                                                             AS subtitle,
    event_ts                                                      AS time,
    image_url,
    kind                                                          AS activity_type,
    multiIf(
        source = 'spotify',  formatReadableTimeDelta(toUnixTimestamp(now()) - toUnixTimestamp(event_ts)),
        source = 'maps',     CASE
                                 WHEN toHour(event_ts) < 12 THEN 'Morning'
                                 WHEN toHour(event_ts) < 18 THEN 'Afternoon'
                                 ELSE 'Evening'
                             END,
        ''
    )                                                             AS metadata,
    is_from_ads
FROM {{ ref('silver_events_unified') }}
QUALIFY recency_rank <= 10
