{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Recent Tracks

    Last 100 played tracks with artist details for the dashboard.
*/

WITH recent_tracks AS (
    SELECT
        track_id,
        track_name,
        track_uri,
        artist_id,
        artist_name,
        artist_uri,
        album_id,
        album_name,
        album_uri,
        track_duration_minutes,
        played_at,
        context_type,
        context_uri
    FROM {{ ref('silver_spotify_tracks') }}
    ORDER BY played_at DESC
    LIMIT 100
),

with_artist_details AS (
    SELECT
        rt.track_id,
        rt.track_name AS track,
        rt.artist_name AS artist,
        toString(rt.played_at) AS played_at,
        rt.album_name AS album,
        ROUND(rt.track_duration_minutes, 2) AS duration_minutes,

        -- Artist details
        COALESCE(ad.image_url, '') AS album_art,
        COALESCE(ad.popularity, 0) AS artist_popularity,
        COALESCE(ad.genres, []) AS genres,

        -- Context
        rt.context_type,
        rt.context_uri,

        ROW_NUMBER() OVER (ORDER BY rt.played_at DESC) AS recency_rank,

        -- Calculate relative time
        CASE
            WHEN dateDiff('hour', rt.played_at, now()) < 1 THEN 'Just now'
            WHEN dateDiff('hour', rt.played_at, now()) < 24 THEN concat(toString(dateDiff('hour', rt.played_at, now())), ' hours ago')
            WHEN dateDiff('hour', rt.played_at, now()) < 48 THEN 'Yesterday'
            WHEN dateDiff('day', rt.played_at, now()) < 7 THEN concat(toString(dateDiff('day', rt.played_at, now())), ' days ago')
            WHEN dateDiff('day', rt.played_at, now()) < 30 THEN concat(toString(dateDiff('week', rt.played_at, now())), ' weeks ago')
            ELSE concat(toString(dateDiff('month', rt.played_at, now())), ' months ago')
        END AS relative_time

    FROM recent_tracks rt
    LEFT JOIN {{ ref('silver_spotify_artists') }} ad
        ON rt.artist_id = ad.artist_id
)

SELECT
    track,
    artist,
    album,
    played_at,
    duration_minutes,
    album_art,
    artist_popularity,
    genres,
    context_type,
    recency_rank,
    relative_time,
    now() AS updated_at

FROM with_artist_details
ORDER BY recency_rank
