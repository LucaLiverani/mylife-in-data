-- /api/youtube/data KPIs. Columns named to match the TS interface.
-- watch_time is an explicit proxy: count × duration_seconds.

{{ config(materialized='view', schema='gold') }}

WITH watches AS (
    SELECT * FROM {{ ref('silver_youtube_watches') }}
),
search AS (
    SELECT * FROM {{ ref('silver_youtube_searches') }}
)
SELECT
    (SELECT count() FROM watches)                                                AS videos_watched,
    (SELECT count() FROM search)                                                 AS total_searches,
    (SELECT countIf(is_from_ads) FROM watches)                                   AS total_ads_watched,
    round(
        (SELECT countIf(is_from_ads) FROM watches) /
        nullIf((SELECT count() FROM watches), 0) * 100.0,
        1
    )                                                                            AS ads_percentage,
    (SELECT sum(duration_seconds) FROM watches)                                  AS total_watch_time_seconds,
    formatReadableTimeDelta((SELECT sum(duration_seconds) FROM watches))         AS total_watch_time_formatted,
    -- avg() over an empty set (e.g. no enriched durations yet) returns NaN;
    -- NaN breaks both toUInt32() (CANNOT_CONVERT_TYPE) and JSON parsing.
    -- ifNotFinite collapses NaN/Inf to 0 so the row is always serialisable.
    ifNotFinite(
        round((SELECT avg(duration_seconds) FROM watches WHERE duration_seconds > 0), 0),
        0
    )                                                                            AS avg_watch_time_seconds,
    formatReadableTimeDelta(
        toUInt32(ifNotFinite(
            round((SELECT avg(duration_seconds) FROM watches WHERE duration_seconds > 0), 0),
            0
        ))
    )                                                                            AS avg_watch_time_formatted,
    (SELECT uniqExact(channel_id) FROM watches WHERE channel_id != '')           AS unique_channels,
    (SELECT uniqExact(video_id) FROM watches)                                    AS unique_videos,
    (SELECT uniqExact(category_id) FROM watches WHERE category_id != '')         AS unique_categories,
    round(
        (SELECT count() FROM watches) /
        nullIf((SELECT uniqExact(watched_date) FROM watches), 0),
        1
    )                                                                            AS avg_activities_per_day,
    round(
        (SELECT count() FROM watches) /
        nullIf((SELECT uniqExact(watched_date) FROM watches), 0),
        1
    )                                                                            AS avg_watched_per_day,
    round(
        (SELECT countIf(duration_seconds > 0) FROM watches) /
        nullIf((SELECT count() FROM watches), 0) * 100.0,
        1
    )                                                                            AS enrichment_percentage,
    toString((SELECT min(watched_date) FROM watches))                            AS first_activity_date,
    toString((SELECT max(watched_date) FROM watches))                            AS last_activity_date
