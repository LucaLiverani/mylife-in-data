-- Per-day listening hours over the last 30 days (matches the dashboard's
-- "Daily listening hours · last 30 days" label). Handler reads {date, hours}.

{{ config(materialized='view', schema='gold') }}

SELECT
    toDate(played_at)                                          AS date,
    round(sum(duration_ms) / 3600000.0, 1)                     AS hours
FROM {{ ref('silver_spotify_plays') }}
WHERE played_at >= today() - 29 AND played_at <= now()
GROUP BY date
ORDER BY date
