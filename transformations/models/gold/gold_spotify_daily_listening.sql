-- Per-day listening hours, last 90 days. Handler reads {date, hours}.

{{ config(materialized='view', schema='gold') }}

SELECT
    toDate(played_at)                                          AS date,
    round(sum(duration_ms) / 3600000.0, 1)                     AS hours
FROM {{ ref('silver_spotify_plays') }}
WHERE played_at >= today() - 90
GROUP BY date
ORDER BY date
