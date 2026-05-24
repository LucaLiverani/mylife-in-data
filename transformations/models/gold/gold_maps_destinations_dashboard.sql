-- Top 10 destinations. Handler keys: destination, count, type.

{{ config(materialized='view', schema='gold') }}

SELECT
    place_name                                  AS destination,
    count()                                     AS count,
    CASE
        WHEN avg(dwell_seconds) >= 3600 THEN 'extended'
        WHEN avg(dwell_seconds) >= 600  THEN 'frequent'
        ELSE 'passing'
    END                                         AS type
FROM {{ ref('silver_maps_visits') }}
WHERE place_name != ''
GROUP BY place_name
ORDER BY count DESC
LIMIT 10
