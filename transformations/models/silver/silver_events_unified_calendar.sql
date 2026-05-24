-- Project Calendar meetings into events_unified.

{{ config(materialized='view', schema='silver') }}

SELECT
    started_at                                         AS event_ts,
    CAST('calendar' AS String)                         AS source,
    CAST('meeting' AS String)                          AS kind,
    title                                              AS title,
    category                                           AS subtitle,
    CAST('' AS String)                                 AS image_url,
    toUInt8(0)                                         AS is_from_ads,
    toJSONString(
        map(
            'duration_minutes', toString(duration_minutes),
            'location', location,
            'attendee_count', toString(attendee_count)
        )
    )                                                  AS metadata,
    generateUUIDv4()                                   AS event_id
FROM {{ ref('silver_calendar_events') }}
