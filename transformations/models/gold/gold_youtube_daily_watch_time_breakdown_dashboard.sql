-- Per-day breakdown by activity (watched / searches / visits / ads / other),
-- with totals + day_name + is_weekend flag.

{{ config(materialized='view', schema='gold') }}

WITH watches AS (
    SELECT * FROM {{ ref('silver_youtube_watches') }}
),
searches AS (
    SELECT * FROM {{ ref('silver_youtube_searches') }}
),
watch_per_day AS (
    SELECT
        watched_date AS date,
        countIf(NOT is_from_ads) AS watched_count,
        countIf(is_from_ads)     AS ads_count,
        sumIf(duration_seconds, NOT is_from_ads) AS watched_seconds,
        sumIf(duration_seconds, is_from_ads)     AS ads_seconds
    FROM watches
    WHERE watched_date >= today() - 29 AND watched_date <= today()
    GROUP BY watched_date
),
search_per_day AS (
    SELECT searched_date AS date, count() AS searches_count
    FROM searches
    WHERE searched_date >= today() - 29 AND searched_date <= today()
    GROUP BY searched_date
),
all_dates AS (
    SELECT date FROM watch_per_day
    UNION DISTINCT
    SELECT date FROM search_per_day
)
SELECT
    ad.date                                                            AS date,
    round(coalesce(w.watched_seconds, 0) / 3600.0, 2)                  AS watched_hours,
    0.0                                                                AS searches_hours,
    0.0                                                                AS visits_hours,
    round(coalesce(w.ads_seconds, 0) / 3600.0, 2)                      AS ads_hours,
    0.0                                                                AS other_hours,
    round(coalesce(w.watched_seconds + w.ads_seconds, 0) / 3600.0, 2)  AS total_hours,
    coalesce(w.watched_count, toUInt64(0))                             AS watched_count,
    coalesce(s.searches_count, toUInt64(0))                            AS searches_count,
    toUInt64(0)                                                        AS visits_count,
    coalesce(w.ads_count, toUInt64(0))                                 AS ads_count,
    arrayElement(
        ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
        toDayOfWeek(ad.date)
    )                                                                  AS day_name,
    toUInt8(toDayOfWeek(ad.date) IN (6,7))                             AS is_weekend
FROM all_dates ad
LEFT JOIN watch_per_day w ON w.date = ad.date
LEFT JOIN search_per_day s ON s.date = ad.date
ORDER BY date
