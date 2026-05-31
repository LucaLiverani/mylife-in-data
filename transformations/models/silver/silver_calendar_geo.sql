-- Calendar events as a TRAVEL-CORROBORATION signal for trip inference.
--
-- silver.maps_trips holds geometric trip candidates (runs of away-days derived
-- from Maps activity). Calendar events independently witness the same travel:
-- a "Flight to Lisbon", a multi-day "Holidays in Portugal" block, a hotel
-- booking. This model geocodes each event's free-text `location` through the
-- SHARED place catalog (the exact q:<text> key the Maps enrichment uses, so a
-- calendar "Zürich" and a Maps "Zürich" resolve to the same catalog row),
-- measures distance from home, and derives travel flags. Phase 5's LLM trip
-- adjudication reads the events that fall inside a trip window as evidence —
-- turning a geometric away-run into a named, classified trip.
--
-- Geocoding is best-effort: an un-geocoded location still yields a title-based
-- travel signal (is_travel_title), so the model is useful before the catalog
-- is warm. Cancelled events are already dropped upstream by silver_calendar_events.

{{ config(materialized='view', schema='silver') }}

WITH events AS (
    SELECT
        event_id, calendar_id, calendar_name, category,
        started_at, ended_at, event_date, title, description, location,
        attendee_count, duration_minutes, is_all_day,
        -- Catalog join key: mirror silver.maps_activity_keyed EXACTLY (lowercase,
        -- whitespace-collapsed, 'q:' prefix) so calendar + maps text converge.
        if(location != '',
           concat('q:', trimBoth(replaceRegexpAll(lowerUTF8(location), '[[:space:]]+', ' '))),
           '')                                                          AS loc_key
    FROM {{ ref('silver_calendar_events') }}
),
catalog AS (
    -- FINAL to collapse the ReplacingMergeTree; drop negative-cache sentinels
    -- (match_type='unresolved', lat/lng=0) so they don't fake a (0,0) location.
    SELECT place_id, locality, country, country_code, lat, lng, match_confidence
    FROM {{ source('bronze', 'maps_place_catalog') }} FINAL
    WHERE match_type != 'unresolved'
),
home AS (
    SELECT home_locality, home_country, home_lat, home_lng
    FROM {{ ref('silver_home_base') }}
),
joined AS (
    SELECT
        e.event_id            AS event_id,
        e.calendar_id         AS calendar_id,
        e.calendar_name       AS calendar_name,
        e.category            AS category,
        e.started_at          AS started_at,
        e.ended_at            AS ended_at,
        e.event_date          AS event_date,
        e.title               AS title,
        e.location            AS location,
        e.attendee_count      AS attendee_count,
        e.duration_minutes    AS duration_minutes,
        e.is_all_day          AS is_all_day,
        c.locality            AS geo_locality,
        c.country             AS geo_country,
        c.country_code        AS geo_country_code,
        c.lat                 AS lat,
        c.lng                 AS lng,
        coalesce(c.match_confidence, toFloat32(0)) AS match_confidence,
        h.home_country        AS home_country,
        h.home_lat            AS home_lat,
        h.home_lng            AS home_lng
    FROM events e
    LEFT JOIN catalog c ON c.place_id = e.loc_key
    CROSS JOIN home h
)
SELECT
    event_id,
    calendar_id,
    calendar_name,
    category,
    started_at,
    ended_at,
    event_date,
    title,
    location,
    attendee_count,
    duration_minutes,
    is_all_day,
    geo_locality,
    geo_country,
    geo_country_code,
    lat,
    lng,
    match_confidence,
    home_country,
    -- 0 when un-geocoded (lat=lng=0) — don't report a spurious ~home distance.
    if(lat != 0 OR lng != 0,
       round(greatCircleDistance(lng, lat, home_lng, home_lat) / 1000.0, 1),
       toFloat64(0))                                                    AS km_from_home,
    -- Spans more than one calendar day (multi-day trip block / holiday).
    toUInt8(toDate(ended_at) > toDate(started_at))                     AS is_multi_day,
    -- Travel-keyword title (case-insensitive, RE2). 'holiday' also matches the
    -- public-holiday subscription calendars — a weak signal on its own, which is
    -- why corroborates_travel also weighs geocoded foreign / far presence.
    toUInt8(match(lowerUTF8(title),
        '(flight|fly to|airport|boarding|layover|✈|hotel|airbnb|hostel|check[ -]?in|check[ -]?out|trip to|travel to|vacation|holiday|getaway|cruise|train to|ferry|road trip)')) AS is_travel_title,
    -- Geocoded to a foreign country.
    toUInt8(geo_country != '' AND geo_country != home_country)         AS is_foreign,
    -- Geocoded >100km from home.
    toUInt8(lat != 0 AND lng != 0
        AND greatCircleDistance(lng, lat, home_lng, home_lat) > 100000) AS is_far,
    -- Any single travel signal. Consumed as a hint; the LLM (Phase 5) sees the
    -- full evidence set and makes the final call.
    toUInt8(
        match(lowerUTF8(title),
            '(flight|fly to|airport|boarding|layover|✈|hotel|airbnb|hostel|check[ -]?in|check[ -]?out|trip to|travel to|vacation|holiday|getaway|cruise|train to|ferry|road trip)')
        OR (geo_country != '' AND geo_country != home_country)
        OR (lat != 0 AND lng != 0
            AND greatCircleDistance(lng, lat, home_lng, home_lat) > 100000)
    )                                                                  AS corroborates_travel
FROM joined
