-- One row per watch event, joined with video + channel catalogs.

{{ config(materialized='view', schema='silver') }}

WITH watches AS (
    SELECT * FROM {{ source('bronze', 'youtube_watch_history') }} FINAL
),
videos AS (
    SELECT * FROM {{ source('bronze', 'youtube_videos') }} FINAL
),
channels AS (
    SELECT * FROM {{ source('bronze', 'youtube_channels') }} FINAL
)
-- NOTE: ClickHouse LEFT JOIN fills unmatched right-side String columns with
-- '' (the column default), NOT NULL — so coalesce(v.col, w.col) keeps the
-- empty '' and silently drops the bronze fallback. Use if(v.col != '', …)
-- instead so watch-history's own channel_id/title survive until the enricher
-- fills bronze.youtube_videos.
SELECT
    w.watched_at                                                       AS watched_at,
    w.video_id                                                         AS video_id,
    if(v.video_title != '', v.video_title, w.video_title)              AS video_title,
    w.video_url                                                        AS video_url,
    if(v.channel_id != '', v.channel_id, w.channel_id)                 AS channel_id,
    if(ch.channel_title != '', ch.channel_title, w.channel_title)      AS channel_title,
    w.activity_type                                                    AS activity_type,
    w.is_from_ads                                                      AS is_from_ads,
    coalesce(v.duration_seconds, 0)                                    AS duration_seconds,
    coalesce(v.category_id, '')                                        AS category_id,
    toDate(w.watched_at)                                               AS watched_date,
    toHour(w.watched_at)                                               AS watched_hour
FROM watches w
LEFT JOIN videos v ON v.video_id = w.video_id
LEFT JOIN channels ch ON ch.channel_id = if(v.channel_id != '', v.channel_id, w.channel_id)
