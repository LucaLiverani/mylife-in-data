-- Project Maps activity into events_unified. Only non-private activity.
-- Each row carries a JSON metadata payload with neighborhood + type so the
-- timeline feed can render appropriately.

{{ config(materialized='view', schema='silver') }}

SELECT
    event_ts                                          AS event_ts,
    CAST('maps' AS String)                            AS source,
    -- Cross-source `kind` uses 'place_visit' historically; keep it for
    -- the dashboard's existing categorisation even though these are now
    -- activity events rather than literal visits.
    multiIf(
        activity_type = 'search',     'maps_search',
        activity_type = 'directions', 'maps_directions',
        activity_type = 'view_place', 'maps_view',
        'maps_other'
    )                                                 AS kind,
    coalesce(nullIf(place_name, ''), query, 'Maps activity') AS title,
    primary_type                                      AS subtitle,
    CAST('' AS String)                                AS image_url,
    toUInt8(0)                                        AS is_from_ads,
    toJSONString(
        map(
            'neighborhood', neighborhood,
            'locality', locality,
            'country', country,
            'primary_type', primary_type,
            'activity_type', activity_type
        )
    )                                                 AS metadata,
    generateUUIDv4()                                  AS event_id
FROM {{ ref('silver_maps_activity_enriched') }}
WHERE is_private = 0
