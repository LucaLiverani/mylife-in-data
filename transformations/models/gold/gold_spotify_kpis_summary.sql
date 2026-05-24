-- One row of cross-time KPIs for /api/spotify/summary.
-- The TS handler expects `artists`, `songs`, `total_hours` (string).

{{ config(materialized='view', schema='gold') }}

SELECT
    uniqExact(primary_artist_id)                                                  AS artists,
    uniqExact(track_id)                                                           AS songs,
    concat(toString(round(sum(duration_ms) / 3600000.0, 1)), ' hrs')              AS total_hours
FROM {{ ref('silver_spotify_plays') }}
