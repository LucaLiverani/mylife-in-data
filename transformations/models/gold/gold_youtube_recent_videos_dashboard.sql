-- Last 10 YouTube videos watched. Handler keys: title, time, relative_time,
-- time_of_day, is_from_ads.

{{ config(materialized='view', schema='gold') }}

SELECT
    video_title                                                          AS title,
    watched_at                                                           AS time,
    formatReadableTimeDelta(toUnixTimestamp(now()) - toUnixTimestamp(watched_at)) AS relative_time,
    CASE
        WHEN watched_hour < 12 THEN 'Morning'
        WHEN watched_hour < 18 THEN 'Afternoon'
        ELSE 'Evening'
    END                                                                  AS time_of_day,
    toUInt8(is_from_ads)                                                 AS is_from_ads
FROM {{ ref('silver_youtube_watches') }}
ORDER BY watched_at DESC
LIMIT 10
