{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Spotify Current Track View

    Pass-through view of the most recent Spotify track from bronze Kafka table.
    Used by the real-time polling endpoint for the dashboard.

    Dashboard Use:
    - Simple SELECT * query with LIMIT 1
    - Provides real-time current playing track
*/

SELECT
    track_id,
    track_name,
    track_uri,
    album_id,
    album_name,
    album_uri,
    album_images,
    artist_id,
    artist_name,
    artist_uri,
    artists_ids,
    artists_names,
    is_playing,
    captured_at,
    progress_ms,
    track_duration_ms,
    device_id,
    device_name,
    device_type,
    device_volume_percent,
    context_type,
    context_uri

FROM {{ source('bronze', 'raw_spotify_current_track_kafka') }}
ORDER BY captured_at DESC
