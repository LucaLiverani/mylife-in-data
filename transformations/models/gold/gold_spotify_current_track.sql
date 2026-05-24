-- Latest currently-playing track, shaped for /api/spotify/current.
-- One row, columns match the TS handler's ClickHouseTrackRow.
--
-- Implemented as a view so the row updates the instant the producer emits.

{{
  config(
    materialized='view',
    schema='gold'
  )
}}

SELECT
    captured_at                                        AS captured_at,
    track_id,
    track_name,
    track_uri,
    album_id,
    album_name,
    album_uri,
    album_images,
    artists_ids[1]                                     AS artist_id,
    arrayElement(artists_names, 1)                     AS artist_name,
    concat('spotify:artist:', artists_ids[1])          AS artist_uri,
    artists_ids,
    artists_names,
    is_playing,
    progress_ms,
    track_duration_ms,
    device_id,
    device_name,
    device_type,
    device_volume_percent,
    context_type,
    context_uri
FROM {{ source('bronze', 'spotify_player_current') }} FINAL
ORDER BY captured_at DESC
LIMIT 1
