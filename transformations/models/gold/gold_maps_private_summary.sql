-- Anonymized counter for friends-related Maps activity. Aggregated count
-- only — no addresses, no names, no neighborhoods. Lets the dashboard show
-- "X interactions with private places this period" without leaking which.

{{ config(materialized='view', schema='gold') }}

SELECT
    countIf(is_private = 1)                              AS private_count,
    countIf(is_private = 1 AND event_date >= today() - 30)   AS private_count_30d
FROM {{ ref('silver_maps_activity_enriched') }}
