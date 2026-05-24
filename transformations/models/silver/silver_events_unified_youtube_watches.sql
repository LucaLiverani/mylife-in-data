-- Project YouTube watch events into events_unified.

{{ config(materialized='view', schema='silver') }}

SELECT
    watched_at                                         AS event_ts,
    CAST('youtube' AS String)                          AS source,
    CAST('watch' AS String)                            AS kind,
    video_title                                        AS title,
    channel_title                                      AS subtitle,
    CAST('' AS String)                                 AS image_url,
    toUInt8(is_from_ads)                               AS is_from_ads,
    toJSONString(
        map(
            'category_id', category_id,
            'duration_seconds', toString(duration_seconds)
        )
    )                                                  AS metadata,
    generateUUIDv4()                                   AS event_id
FROM {{ ref('silver_youtube_watches') }}
WHERE video_id != ''
