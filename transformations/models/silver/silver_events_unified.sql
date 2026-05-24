-- Union all per-source events_unified projections into a single view.
-- New sources land here by adding another SELECT below — silver/gold downstream
-- doesn't change.

{{ config(materialized='view', schema='silver') }}

SELECT * FROM {{ ref('silver_events_unified_spotify_plays') }}
UNION ALL
SELECT * FROM {{ ref('silver_events_unified_spotify_liked') }}
UNION ALL
SELECT * FROM {{ ref('silver_events_unified_maps_visits') }}
