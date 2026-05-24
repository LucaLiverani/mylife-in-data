-- Last 10 Maps activities. Handler keys: time, location, type, timeOfDay.

{{ config(materialized='view', schema='gold') }}

SELECT
    started_at                                                       AS time,
    place_name                                                       AS location,
    CASE
        WHEN dwell_seconds >= 3600 THEN 'extended visit'
        WHEN dwell_seconds >= 600  THEN 'short stop'
        ELSE 'passing through'
    END                                                              AS type,
    CASE
        WHEN hour_of_day < 12 THEN 'Morning'
        WHEN hour_of_day < 18 THEN 'Afternoon'
        ELSE 'Evening'
    END                                                              AS timeOfDay
FROM {{ ref('silver_maps_visits') }}
ORDER BY started_at DESC
LIMIT 10
