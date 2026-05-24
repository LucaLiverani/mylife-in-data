-- Last 50 plays, shaped for /api/spotify/recent.
-- Handler maps played_at → time, relative_time → relativeTime.

{{ config(materialized='view', schema='gold') }}

SELECT
    track_name                                                AS track,
    primary_artist_name                                       AS artist,
    played_at                                                 AS played_at,
    album_art_url                                             AS album_art,
    formatReadableTimeDelta(toUnixTimestamp(now()) - toUnixTimestamp(played_at))
                                                              AS relative_time
FROM {{ ref('silver_spotify_plays') }}
ORDER BY played_at DESC
LIMIT 50
