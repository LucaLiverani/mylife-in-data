-- Cross-references bronze.maps_activity with the place catalog for type +
-- neighborhood, and with the private-places filter (haversine ≤ radius_m).
-- is_private = 1 means the activity lat/lng matches a starred place (friend's
-- house). Gold tables aggregate WHERE is_private = 0 and report the private
-- count separately as an anonymized "friends" counter.

{{ config(materialized='view', schema='silver') }}

WITH activity AS (
    -- silver.maps_activity_keyed (DDL view, warehouse/ddl/51_maps_activity.sql)
    -- adds best_text + geo_key. geo_key is the catalog join key: the URL ftid
    -- when present, else a normalized-text key — so the ~all text-only
    -- activities (which have no ftid) still resolve to a catalog row.
    SELECT * FROM silver.maps_activity_keyed
),
catalog AS (
    SELECT * FROM {{ source('bronze', 'maps_place_catalog') }} FINAL
),
-- Aggregate all private places into a single row of three parallel arrays.
-- ClickHouse rejects correlated EXISTS subqueries that reference outer-scope
-- columns ("Resolve identifier 'e.lat' from parent scope only supported for
-- constants and CTE"), so we cross-join this 1-row aggregate against the
-- enriched activity rows and use arrayExists() to scan for a match.
-- When silver.maps_private_places is empty, the arrays are empty too and
-- arrayExists returns 0 (correct: no private rows to flag).
private_places_arr AS (
    SELECT
        groupArray(lat)      AS p_lats,
        groupArray(lng)      AS p_lngs,
        groupArray(radius_m) AS p_radii
    FROM silver.maps_private_places FINAL
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
    LEFT JOIN catalog c ON c.place_id = a.geo_key
)
SELECT
    e.*,
    -- Spatial check against private-places. Haversine in km, compared to
    -- radius_m/1000. Short-circuits on first match within the array.
    toUInt8(arrayExists(
        i ->
            e.lat != 0 AND e.lng != 0
            AND 6371.0 * 2 * asin(
                    sqrt(
                        pow(sin((pp.p_lats[i] - e.lat) * pi() / 360), 2) +
                        cos(e.lat * pi() / 180) * cos(pp.p_lats[i] * pi() / 180) *
                        pow(sin((pp.p_lngs[i] - e.lng) * pi() / 360), 2)
                    )
                ) <= (pp.p_radii[i] / 1000.0),
        range(1, length(pp.p_lats) + 1)
    ))                                                   AS is_private
FROM enriched e
CROSS JOIN private_places_arr pp
