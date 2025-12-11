{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Watch Time Breakdown

    Daily time series showing estimated hours spent on different activity types.

    Watch time estimation approach:
    - Assumes 60% average completion rate for videos (realistic based on YouTube analytics)
    - Caps daily total at 18 hours (maximum realistic watch time per day)
    - Only counts videos with enriched duration data
*/

WITH daily_raw AS (
    SELECT
        activity_date AS date,

        -- Calculate raw watch time with 60% completion rate assumption
        SUM(CASE
            WHEN activity_type = 'watched' AND duration_seconds IS NOT NULL
            THEN duration_seconds * 0.6  -- Assume 60% completion rate
            ELSE 0
        END) / 3600.0 AS raw_watched_hours,

        -- Ads watch time (assume full duration since they're short)
        SUM(CASE
            WHEN is_from_ads = 1 AND duration_seconds IS NOT NULL
            THEN duration_seconds
            ELSE 0
        END) / 3600.0 AS raw_ads_hours,

        -- Searches and visits (small estimates)
        SUM(CASE WHEN activity_type = 'search' THEN 0.05 ELSE 0 END) AS raw_searches_hours,
        SUM(CASE WHEN activity_type = 'visit' THEN 0.02 ELSE 0 END) AS raw_visits_hours,

        -- Other activities
        SUM(CASE
            WHEN activity_type NOT IN ('watched', 'search', 'visit') AND duration_seconds IS NOT NULL
            THEN duration_seconds * 0.6
            ELSE 0
        END) / 3600.0 AS raw_other_hours,

        -- Activity counts for reference
        countIf(activity_type = 'watched') AS watched_count,
        countIf(activity_type = 'search') AS searches_count,
        countIf(activity_type = 'visit') AS visits_count,
        countIf(is_from_ads = 1) AS ads_count,

        -- Day metadata
        any(dateName('weekday', activity_date)) AS day_name,
        CASE WHEN toDayOfWeek(activity_date) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend

    FROM {{ ref('silver_youtube_watch_history_enriched') }}
    GROUP BY activity_date
)

SELECT
    date,

    -- Cap total daily watch time at 18 hours (realistic maximum)
    -- If raw total exceeds 18h, proportionally scale down all activities
    CASE
        WHEN (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours) > 18
        THEN ROUND(raw_watched_hours * 18.0 / (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours), 2)
        ELSE ROUND(raw_watched_hours, 2)
    END AS watched_hours,

    CASE
        WHEN (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours) > 18
        THEN ROUND(raw_searches_hours * 18.0 / (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours), 2)
        ELSE ROUND(raw_searches_hours, 2)
    END AS searches_hours,

    CASE
        WHEN (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours) > 18
        THEN ROUND(raw_visits_hours * 18.0 / (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours), 2)
        ELSE ROUND(raw_visits_hours, 2)
    END AS visits_hours,

    CASE
        WHEN (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours) > 18
        THEN ROUND(raw_ads_hours * 18.0 / (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours), 2)
        ELSE ROUND(raw_ads_hours, 2)
    END AS ads_hours,

    CASE
        WHEN (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours) > 18
        THEN ROUND(raw_other_hours * 18.0 / (raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours), 2)
        ELSE ROUND(raw_other_hours, 2)
    END AS other_hours,

    -- Total hours (capped at 18)
    LEAST(
        ROUND(raw_watched_hours + raw_ads_hours + raw_searches_hours + raw_visits_hours + raw_other_hours, 2),
        18.0
    ) AS total_hours,

    -- Activity counts
    watched_count,
    searches_count,
    visits_count,
    ads_count,
    day_name,
    is_weekend

FROM daily_raw
ORDER BY date DESC
