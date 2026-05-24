-- Top 15 artists with 30-day per-day play counts as `trend`.
-- Handler keys: rank, name, plays, hours, genre.

{{ config(materialized='view', schema='gold') }}

WITH artists AS (
    SELECT
        primary_artist_id,
        any(primary_artist_name)                              AS name,
        any(genres)                                           AS genres,
        count()                                               AS plays,
        round(sum(duration_ms) / 3600000.0, 1)                AS hours
    FROM {{ ref('silver_spotify_plays') }}
    WHERE primary_artist_id != ''
    GROUP BY primary_artist_id
),
daily_by_artist AS (
    SELECT
        primary_artist_id,
        toDate(played_at)                                     AS d,
        count()                                               AS c
    FROM {{ ref('silver_spotify_plays') }}
    WHERE played_at >= today() - 29
    GROUP BY primary_artist_id, d
),
trend AS (
    SELECT
        primary_artist_id,
        arrayMap(
            i -> coalesce(any(c) FILTER (WHERE d = today() - 29 + i), 0),
            range(30)
        )                                                     AS trend
    FROM daily_by_artist
    GROUP BY primary_artist_id
)
SELECT
    row_number() OVER (ORDER BY a.plays DESC, a.name)                     AS rank,
    a.name                                                                AS name,
    a.plays                                                               AS plays,
    a.hours                                                               AS hours,
    arrayElement(a.genres, 1)                                             AS genre,
    coalesce(t.trend, arrayMap(i -> 0, range(30)))                        AS trend
FROM artists a
LEFT JOIN trend t USING (primary_artist_id)
ORDER BY a.plays DESC, a.name
LIMIT 15
