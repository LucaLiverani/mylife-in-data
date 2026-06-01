-- Top neighborhoods you searched/viewed (aggregated, no per-place detail).

{{ config(materialized='view', schema='gold') }}

SELECT
    multiIf(
        neighborhood != '' AND locality != '', concat(neighborhood, ', ', locality),
        locality != '',                        locality,
        country != '',                         country,
        'Unknown'
    )                                                AS destination,
    count()                                          AS count,
    anyHeavy(primary_type)                           AS type
FROM {{ ref('silver_maps_activity_enriched') }}
WHERE is_private = 0
  AND event_date >= toDate('{{ var("kpi_start_date") }}')
  AND country IN (
      SELECT DISTINCT country FROM {{ ref('silver_maps_activity_enriched') }}
      WHERE is_private = 0 AND activity_type = 'directions' AND country != ''
        AND event_date >= toDate('{{ var("kpi_start_date") }}')
  )
GROUP BY destination
HAVING destination != 'Unknown'
ORDER BY count DESC
LIMIT 10
