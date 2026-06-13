-- Last 50 plays, shaped for /api/spotify/recent.
-- Handler maps played_at → time. Relative time ("4m ago") is rendered
-- client-side from the timestamp, so it stays fresh and compact on mobile.

{{ config(materialized='view', schema='gold') }}

SELECT
    track,
    artist,
    -- ISO-8601 UTC ('…Z') so the browser's `new Date()` parses it as UTC,
    -- not local. NB: ClickHouse %i is minutes; %M is the month NAME.
    formatDateTime(played_at_raw, '%Y-%m-%dT%H:%i:%SZ', 'UTC') AS played_at,
    album_art
FROM (
    -- Order + LIMIT on the raw DateTime in the inner query: aliasing the
    -- formatted string to `played_at` in the outer SELECT would make an
    -- outer ORDER BY bind to the string (ClickHouse prefers aliases).
    SELECT
        track_name           AS track,
        primary_artist_name  AS artist,
        played_at            AS played_at_raw,
        album_art_url        AS album_art
    FROM {{ ref('silver_spotify_plays_merged') }}
    ORDER BY played_at_raw DESC
    LIMIT 50
)
-- Display order only; the recency window is fixed by the inner LIMIT.
ORDER BY played_at DESC
