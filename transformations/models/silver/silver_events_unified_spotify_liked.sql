-- Project Spotify Liked events into events_unified.

{{ config(materialized='view', schema='silver') }}

SELECT
    added_at                                           AS event_ts,
    CAST('spotify' AS String)                          AS source,
    CAST('liked' AS String)                            AS kind,
    track_name                                         AS title,
    primary_artist_name                                AS subtitle,
    album_art_url                                      AS image_url,
    toUInt8(0)                                         AS is_from_ads,
    toJSONString(map('source', 'spotify_liked'))       AS metadata,
    generateUUIDv4()                                   AS event_id
FROM {{ ref('silver_spotify_saved') }}
WHERE track_id != ''
