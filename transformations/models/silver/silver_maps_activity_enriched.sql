-- Cross-references bronze.maps_activity with the place catalog for type +
-- neighborhood, and with the private-places filter (haversine ≤ radius_m).
-- is_private = 1 means the activity lat/lng matches a starred place (friend's
-- house). Gold tables aggregate WHERE is_private = 0 and report the private
-- count separately as an anonymized "friends" counter.

{{ config(materialized='view', schema='silver') }}

WITH activity AS (
    SELECT * FROM {{ source('bronze', 'maps_activity') }} FINAL
),
catalog AS (
    SELECT * FROM {{ source('bronze', 'maps_place_catalog') }} FINAL
),
private_places AS (
    SELECT * FROM silver.maps_private_places FINAL
),
enriched AS (
    SELECT
        a.event_ts                                       AS event_ts,
        a.activity_type                                  AS activity_type,
        a.query                                          AS query,
        coalesce(c.place_name, a.place_name)             AS place_name,
        a.place_id                                       AS place_id,
        coalesce(c.primary_type, '')                     AS primary_type,
        c.place_types                                    AS place_types,
        -- Prefer catalog coords (they were normalised by the API); fall back
        -- to whatever the raw URL had.
        coalesce(c.lat, a.lat)                           AS lat,
        coalesce(c.lng, a.lng)                           AS lng,
        coalesce(c.neighborhood, '')                     AS neighborhood,
        coalesce(c.sublocality, '')                      AS sublocality,
        coalesce(c.locality, '')                         AS locality,
        coalesce(c.country, '')                          AS country,
        coalesce(c.country_code, '')                     AS country_code,
        a.origin                                         AS origin,
        a.destination                                    AS destination,
        toDate(a.event_ts)                               AS event_date,
        toHour(a.event_ts)                               AS hour_of_day
    FROM activity a
    LEFT JOIN catalog c ON c.place_id = a.place_id
)
SELECT
    e.*,
    -- Spatial check against private-places. Haversine in km, compared to
    -- radius_m/1000. EXISTS subquery short-circuits on first match.
    toUInt8(EXISTS (
        SELECT 1 FROM private_places p
        WHERE e.lat != 0 AND e.lng != 0
          AND 6371.0 * 2 * asin(
                sqrt(
                    pow(sin((p.lat - e.lat) * pi() / 360), 2) +
                    cos(e.lat * pi() / 180) * cos(p.lat * pi() / 180) *
                    pow(sin((p.lng - e.lng) * pi() / 360), 2)
                )
            ) <= (p.radius_m / 1000.0)
    ))                                                   AS is_private
FROM enriched e
