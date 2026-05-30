-- Top 15 artists with 30-day per-day play counts as `trend`.
-- Handler keys: rank, name, plays, hours, genre, trend.

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
-- Per-artist daily play counts over the last 30 days, indexed 0..29 by the
-- offset from (today - 29). day_idx is the array position the count lands in.
daily_by_artist AS (
    SELECT
        primary_artist_id,
        toInt32(toDate(played_at) - (today() - 29))           AS day_idx,
        count()                                               AS c
    FROM {{ ref('silver_spotify_plays') }}
    WHERE played_at >= today() - 29
    GROUP BY primary_artist_id, day_idx
),
-- groupArrayInsertAt(default, size)(value, pos) builds a fixed-length 30-slot
-- array, filling untouched days with 0. This replaces the previous
-- arrayMap(i -> aggregate FILTER ...) form, which referenced the lambda var
-- `i` inside an aggregate under GROUP BY (illegal → NOT_FOUND_COLUMN).
trend AS (
    SELECT
        primary_artist_id,
        groupArrayInsertAt(toUInt64(0), 30)(c, toUInt32(day_idx)) AS trend
    FROM daily_by_artist
    WHERE day_idx >= 0 AND day_idx < 30
    GROUP BY primary_artist_id
)
SELECT
    row_number() OVER (ORDER BY a.plays DESC, a.name)                     AS rank,
    a.name                                                                AS name,
    a.plays                                                               AS plays,
    a.hours                                                               AS hours,
    arrayElement(a.genres, 1)                                             AS genre,
    if(length(t.trend) = 30, t.trend, arrayMap(x -> toUInt64(0), range(30))) AS trend
FROM artists a
LEFT JOIN trend t USING (primary_artist_id)
ORDER BY a.plays DESC, a.name
LIMIT 15
