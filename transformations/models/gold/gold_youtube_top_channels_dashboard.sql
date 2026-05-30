-- Top 10 channels by total watch time (count × duration_seconds).
-- Watch time is a proxy — Google doesn't track partial watches.

{{ config(materialized='view', schema='gold') }}

WITH watches AS (
    SELECT * FROM {{ ref('silver_youtube_watches') }}
),
ranked AS (
    SELECT
        channel_id,
        any(channel_title)                                                          AS channel_title,
        count()                                                                     AS watch_count,
        sum(duration_seconds)                                                       AS total_watch_time_seconds,
        uniqExact(video_id)                                                         AS unique_videos_watched
    FROM watches
    WHERE channel_id != ''
    GROUP BY channel_id
),
cats AS (
    -- Per-channel primary category: the category most frequently watched.
    SELECT channel_id, anyHeavy(category_id) AS top_category_id
    FROM watches
    WHERE channel_id != '' AND category_id != ''
    GROUP BY channel_id
)
SELECT
    r.channel_id                                                                    AS channel_id,
    r.channel_title                                                                 AS channel_title,
    r.watch_count                                                                   AS watch_count,
    r.total_watch_time_seconds                                                      AS total_watch_time_seconds,
    formatReadableTimeDelta(r.total_watch_time_seconds)                             AS total_watch_time_formatted,
    {{ youtube_category_name("coalesce(c.top_category_id, '')") }}                   AS primary_category,
    r.unique_videos_watched                                                         AS unique_videos_watched
FROM ranked r
LEFT JOIN cats c USING (channel_id)
-- watch_count is the tiebreaker so "top channels" is meaningful even before
-- the enricher fills durations (until then total_watch_time_seconds is all 0).
ORDER BY total_watch_time_seconds DESC, watch_count DESC
LIMIT 10
