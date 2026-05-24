-- Map locations with derived `dwell_time_category` and distance_to_next_km.
-- Handler: {name, lat, lng, duration, dwell_time_category, distance_to_next_km}.
-- ClickHouse spells window-fn `lead` as `leadInFrame`.

{{ config(materialized='view', schema='gold') }}

WITH ordered AS (
    SELECT
        place_name                                                       AS name,
        lat,
        lng,
        dwell_seconds,
        started_at,
        leadInFrame(lat) OVER (ORDER BY started_at ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS next_lat,
        leadInFrame(lng) OVER (ORDER BY started_at ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS next_lng
    FROM {{ ref('silver_maps_visits') }}
    WHERE place_name != ''
)
SELECT
    name,
    lat,
    lng,
    formatReadableTimeDelta(dwell_seconds)                                      AS duration,
    multiIf(
        dwell_seconds < 600,    'transient',
        dwell_seconds < 3600,   'short',
        dwell_seconds < 18000,  'medium',
                                'long'
    )                                                                            AS dwell_time_category,
    round(
        6371.0 * 2 * asin(
            sqrt(
                pow(sin((next_lat - lat) * pi() / 360), 2) +
                cos(lat * pi() / 180) * cos(next_lat * pi() / 180) *
                pow(sin((next_lng - lng) * pi() / 360), 2)
            )
        ),
        1
    )                                                                            AS distance_to_next_km
FROM ordered
ORDER BY started_at DESC
LIMIT 500
