-- Silver: deduped + city/country extracted. Address tail = country, second-to-last = city.

{{ config(materialized='view', schema='silver') }}

SELECT
    started_at,
    ended_at,
    place_name,
    place_id,
    place_address,
    lat,
    lng,
    confidence,
    arrayElement(
        arrayMap(s -> trim(BOTH ' ' FROM s), splitByChar(',', place_address)),
        -1
    )                                          AS country,
    arrayElement(
        arrayMap(s -> trim(BOTH ' ' FROM s), splitByChar(',', place_address)),
        -2
    )                                          AS city,
    toDate(started_at)                         AS visit_date,
    toHour(started_at)                         AS hour_of_day,
    dateDiff('second', started_at, ended_at)   AS dwell_seconds
FROM {{ source('bronze', 'maps_visits') }} FINAL
WHERE place_id != '' OR place_name != ''
