{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Genre Distribution

    Aggregates play counts by genre using artist genre tags.
    Flattens array of genres into individual rows.
*/

WITH artist_genres AS (
    SELECT DISTINCT
        artist_id,
        genres
    FROM {{ ref('silver_spotify_artists') }}
    WHERE length(genres) > 0
),

track_plays AS (
    SELECT
        artist_id,
        COUNT(*) AS play_count,
        SUM(track_duration_ms) / 1000.0 / 3600.0 AS total_hours
    FROM {{ ref('silver_spotify_tracks') }}
    GROUP BY artist_id
),

genre_plays AS (
    SELECT
        genre,
        SUM(tp.play_count) AS play_count,
        ROUND(SUM(tp.total_hours), 1) AS total_hours,
        COUNT(DISTINCT tp.artist_id) AS artist_count
    FROM artist_genres ag
    ARRAY JOIN ag.genres AS genre
    LEFT JOIN track_plays tp
        ON ag.artist_id = tp.artist_id
    GROUP BY genre
)

SELECT
    genre AS name,
    play_count AS value,
    total_hours AS hours,
    artist_count AS artists,
    ROUND(play_count * 100.0 / SUM(play_count) OVER (), 1) AS percentage,
    ROW_NUMBER() OVER (ORDER BY play_count DESC) AS rank,
    now() AS updated_at

FROM genre_plays
WHERE genre != ''
ORDER BY play_count DESC
LIMIT 10;
