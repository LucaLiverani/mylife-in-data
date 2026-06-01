-- New tile: activity broken down by place type (restaurant/cafe/museum/...).
-- Not yet wired into the dashboard handler; future-friendly.

{{ config(materialized='view', schema='gold') }}

SELECT
    coalesce(nullIf(primary_type, ''), 'unknown')    AS name,
    count()                                          AS value
FROM {{ ref('silver_maps_activity_enriched') }}
WHERE is_private = 0
  AND event_date >= toDate('{{ var("kpi_start_date") }}')
GROUP BY name
ORDER BY value DESC
LIMIT 20
