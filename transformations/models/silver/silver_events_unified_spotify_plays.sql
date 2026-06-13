-- Project Spotify plays into the cross-source events_unified shape.
-- Materialized as a view (not an MV) so we keep one storage row per logical
-- event; combining UNION ALL across multiple per-source views in
-- silver_events_unified.sql below would mean every gold query touches every
-- source — too expensive. Each per-source view here is what gets UNIONed.

{{ config(materialized='view', schema='silver') }}

SELECT
    played_at                                          AS event_ts,
    CAST('spotify' AS String)                          AS source,
    CAST('play' AS String)                             AS kind,
    track_name                                         AS title,
    primary_artist_name                                AS subtitle,
    album_art_url                                      AS image_url,
    toUInt8(0)                                         AS is_from_ads,
    toJSONString(
        map(
            'context_type', context_type,
            'duration_ms', toString(duration_ms),
            'genres', toString(genres)
        )
    )                                                  AS metadata,
    generateUUIDv4()                                   AS event_id
FROM {{ ref('silver_spotify_plays_merged') }}
WHERE track_id != ''
