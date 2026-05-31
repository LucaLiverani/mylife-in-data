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
    -- A LEFT JOIN miss (track not yet enriched) leaves t.* at column defaults
    -- ('' / 0 / []), not NULL. Prefer the enriched catalog value when present,
    -- else fall back to the metadata captured from the recently-played payload
    -- at ingest — so the freshest plays show a title/artist/art immediately.
    if(t.track_name != '', t.track_name, p.track_name)                AS track_name,
    if(t.duration_ms > 0, t.duration_ms, p.duration_ms)               AS duration_ms,
    arrayElement(p.artists_ids, 1)                                    AS primary_artist_id,
    if(a.artist_name != '', a.artist_name, arrayElement(p.artists_names, 1))  AS primary_artist_name,
    a.genres                                                          AS genres,
    if(t.album_name != '', t.album_name, p.album_name)                AS album_name,
    if(notEmpty(t.album_images), arrayElement(t.album_images, 1), arrayElement(p.album_images, 1)) AS album_art_url,
    p.context_type                                                    AS context_type,
    p.context_uri                                                     AS context_uri
FROM plays p
LEFT JOIN tracks t ON t.track_id = p.track_id
LEFT JOIN artists a ON a.artist_id = arrayElement(p.artists_ids, 1)
