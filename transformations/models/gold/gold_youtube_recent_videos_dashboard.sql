-- Last 10 YouTube videos watched. Handler keys: title, time, is_from_ads.
-- Relative time ("3h ago") and time-of-day labels are rendered client-side
-- from `time`, in the viewer's timezone.

{{ config(materialized='view', schema='gold') }}

SELECT
    video_title                                              AS title,
    -- ISO-8601 UTC ('…Z') so the browser's `new Date()` parses it as UTC,
    -- not local. NB: ClickHouse %i is minutes; %M is the month NAME.
    formatDateTime(watched_at, '%Y-%m-%dT%H:%i:%SZ', 'UTC')  AS time,
    toUInt8(is_from_ads)                                     AS is_from_ads
FROM {{ ref('silver_youtube_watches') }}
ORDER BY watched_at DESC
LIMIT 10
