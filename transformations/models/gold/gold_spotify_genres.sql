-- Genre play counts. Handler reads {name, value}.

{{ config(materialized='view', schema='gold') }}

SELECT
    genre                                                  AS name,
    count()                                                AS value
FROM {{ ref('silver_spotify_plays') }}
ARRAY JOIN genres AS genre
WHERE genre != ''
  AND played_at >= toDateTime('{{ var("kpi_start_date") }}')
GROUP BY genre
ORDER BY value DESC
LIMIT 20
