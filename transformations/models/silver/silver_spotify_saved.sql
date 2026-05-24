-- Silver: passthrough cleanup of saved (Liked) tracks. Joins to track catalog
-- for displayable title + artist.

{{ config(materialized='view', schema='silver') }}

WITH saved AS (
    SELECT * FROM {{ source('bronze', 'spotify_saved_tracks') }} FINAL
),
tracks AS (
    SELECT * FROM {{ source('bronze', 'spotify_tracks') }} FINAL
),
artists AS (
    SELECT * FROM {{ source('bronze', 'spotify_artists') }} FINAL
)
SELECT
    s.added_at                                                        AS added_at,
    s.track_id                                                        AS track_id,
    coalesce(t.track_name, '')                                        AS track_name,
    coalesce(a.artist_name, '')                                       AS primary_artist_name,
    arrayElement(coalesce(t.album_images, []), 1)                     AS album_art_url
FROM saved s
LEFT JOIN tracks t ON t.track_id = s.track_id
LEFT JOIN artists a ON a.artist_id = arrayElement(t.artists_ids, 1)
