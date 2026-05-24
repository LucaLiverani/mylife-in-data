-- One row per play, fully denormalized. Downstream gold tables don't join.
-- Implemented as a view so dedup happens at query time without an MV cycle.

{{ config(materialized='view', schema='silver') }}

WITH plays AS (
    SELECT * FROM {{ source('bronze', 'spotify_plays_raw') }} FINAL
),
tracks AS (
    SELECT * FROM {{ source('bronze', 'spotify_tracks') }} FINAL
),
artists AS (
    SELECT * FROM {{ source('bronze', 'spotify_artists') }} FINAL
)
SELECT
    p.played_at                                                       AS played_at,
    p.track_id                                                        AS track_id,
    coalesce(t.track_name, '')                                        AS track_name,
    coalesce(t.duration_ms, p.duration_ms)                            AS duration_ms,
    arrayElement(p.artists_ids, 1)                                    AS primary_artist_id,
    coalesce(a.artist_name, '')                                       AS primary_artist_name,
    a.genres                                                          AS genres,
    coalesce(t.album_name, '')                                        AS album_name,
    arrayElement(coalesce(t.album_images, []), 1)                     AS album_art_url,
    p.context_type                                                    AS context_type,
    p.context_uri                                                     AS context_uri
FROM plays p
LEFT JOIN tracks t ON t.track_id = p.track_id
LEFT JOIN artists a ON a.artist_id = arrayElement(p.artists_ids, 1)
