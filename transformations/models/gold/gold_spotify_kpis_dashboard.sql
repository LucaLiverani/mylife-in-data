-- KPI row for /api/spotify/data.
-- Columns named to match the handler's destructuring: total_time, songs_streamed,
-- unique_artists, avg_daily.

{{ config(materialized='view', schema='gold') }}

WITH stats AS (
    SELECT
        sum(duration_ms)                       AS total_ms,
        uniqExact(track_id)                    AS songs,
        uniqExact(primary_artist_id)           AS artists,
        uniqExact(toDate(played_at))           AS active_days
    FROM {{ ref('silver_spotify_plays_merged') }}
    WHERE played_at >= toDateTime('{{ var("kpi_start_date") }}')
)
SELECT
    concat(toString(round(total_ms / 3600000.0, 1)), ' hrs')                         AS total_time,
    toString(songs)                                                                  AS songs_streamed,
    toString(artists)                                                                AS unique_artists,
    concat(
        toString(round(total_ms / 3600000.0 / nullIf(active_days, 0), 1)),
        ' hrs'
    )                                                                                AS avg_daily
FROM stats
