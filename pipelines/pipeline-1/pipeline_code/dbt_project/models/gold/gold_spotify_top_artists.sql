{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Top Artists

    Top artists by play count with enriched details from artist dimension.
*/

WITH artist_plays AS (
    SELECT
        artist_id,
        artist_name,
        COUNT(*) AS play_count,
        SUM(track_duration_ms) / 1000.0 / 3600.0 AS total_hours,
        COUNT(DISTINCT track_id) AS unique_tracks,
        MIN(played_at) AS first_played,
        MAX(played_at) AS last_played
    FROM {{ ref('silver_spotify_tracks') }}
    GROUP BY artist_id, artist_name
),

artist_details AS (
    SELECT
        artist_id,
        popularity,
        followers_total,
        genres,
        image_url,
        external_url_spotify
    FROM {{ ref('silver_spotify_artists') }}
),

ranked_artists AS (
    SELECT
        ap.artist_id,
        ap.artist_name,
        ap.play_count,
        ROUND(ap.total_hours, 1) AS hours,
        ap.unique_tracks,
        ap.first_played,
        ap.last_played,

        -- Artist details (if available)
        COALESCE(ad.popularity, 0) AS popularity,
        COALESCE(ad.followers_total, 0) AS followers,
        COALESCE(ad.genres, []) AS genres,
        arrayStringConcat(COALESCE(ad.genres, []), ', ') AS genre,
        COALESCE(ad.image_url, '') AS image_url,
        COALESCE(ad.external_url_spotify, '') AS spotify_url,

        ROW_NUMBER() OVER (ORDER BY play_count DESC) AS rank

    FROM artist_plays ap
    LEFT JOIN artist_details ad
        ON ap.artist_id = ad.artist_id
)

SELECT
    rank,
    artist_id,
    artist_name AS name,
    play_count AS plays,
    hours,
    unique_tracks,
    popularity,
    followers,
    genre,
    genres,
    image_url,
    spotify_url,
    first_played,
    last_played,
    now() AS updated_at

FROM ranked_artists
ORDER BY rank
LIMIT 100
