-- Project Maps place visits into events_unified.

{{ config(materialized='view', schema='silver') }}

SELECT
    started_at                                          AS event_ts,
    CAST('maps' AS String)                              AS source,
    CAST('place_visit' AS String)                       AS kind,
    place_name                                          AS title,
    place_address                                       AS subtitle,
    CAST('' AS String)                                  AS image_url,
    toUInt8(0)                                          AS is_from_ads,
    toJSONString(
        map(
            'lat', toString(lat),
            'lng', toString(lng),
            'dwell_seconds', toString(dwell_seconds)
        )
    )                                                   AS metadata,
    generateUUIDv4()                                    AS event_id
FROM {{ ref('silver_maps_visits') }}
