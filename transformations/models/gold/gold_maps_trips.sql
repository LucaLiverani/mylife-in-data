-- Trip list — populated by silver.maps_trips. Not yet queried by travel/data.ts
-- but exposed for the mock's `trips[]` array.

{{ config(materialized='view', schema='gold') }}

SELECT
    started_at,
    ended_at,
    days,
    destination,
    destination_country,
    km
FROM silver.maps_trips
ORDER BY started_at DESC
