-- Top 15 artists since the shared kpi_start_date, with a per-WEEK play-count
-- sparkline (`trend`) over the same window. Handler keys: rank, name, plays,
-- hours, genre, trend.

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
      AND played_at >= toDateTime('{{ var("kpi_start_date") }}')
    GROUP BY primary_artist_id
),
-- Per-artist weekly play counts from kpi_start_date → today. Bucketing by week
-- (not day) keeps the sparkline readable over the ~17-month window; week 0 is
-- the week containing kpi_start_date.
weekly_by_artist AS (
    SELECT
        primary_artist_id,
        toUInt32(intDiv(toDate(played_at) - toDate('{{ var("kpi_start_date") }}'), 7)) AS week_idx,
        count()                                               AS c
    FROM {{ ref('silver_spotify_plays') }}
    WHERE primary_artist_id != ''
      AND played_at >= toDateTime('{{ var("kpi_start_date") }}')
    GROUP BY primary_artist_id, week_idx
),
-- Densify into a gap-filled array (0 for silent weeks). The number of weeks is
-- derived from the window, so the array grows over time — no hardcoded length.
-- CAST((keys, values) -> Map) + a map lookup over range(weeks) sidesteps
-- groupArrayInsertAt's constant-size requirement.
trend AS (
    SELECT
        primary_artist_id,
        arrayMap(
            w -> toUInt64(m[toUInt32(w)]),
            range(toUInt32(intDiv(today() - toDate('{{ var("kpi_start_date") }}'), 7) + 1))
        )                                                     AS trend
    FROM (
        SELECT
            primary_artist_id,
            CAST((groupArray(week_idx), groupArray(c)), 'Map(UInt32, UInt64)') AS m
        FROM weekly_by_artist
        GROUP BY primary_artist_id
    )
)
SELECT
    row_number() OVER (ORDER BY a.plays DESC, a.name)                     AS rank,
    a.name                                                                AS name,
    a.plays                                                               AS plays,
    a.hours                                                               AS hours,
    arrayElement(a.genres, 1)                                             AS genre,
    -- Every ranked artist has in-window plays, so the join always hits and
    -- trend is the full weekly array.
    t.trend                                                               AS trend
FROM artists a
LEFT JOIN trend t USING (primary_artist_id)
ORDER BY a.plays DESC, a.name
LIMIT 15
