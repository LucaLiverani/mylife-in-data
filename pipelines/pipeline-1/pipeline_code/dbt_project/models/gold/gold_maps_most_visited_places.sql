{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Most Visited Places

    Aggregates location visit data to identify most frequently visited places.
    Includes:
    - Visit count and frequency metrics
    - First and last visit timestamps
    - Average visits per month
    - Location ranking
    - Visit pattern insights (weekend/weekday, time of day)
*/

WITH location_visits AS (
    SELECT
        location_name,
        location_address,
        location_url,
        latitude,
        longitude,
        activity_time,
        activity_date,
        day_of_week,
        is_weekend,
        time_of_day,
        month_start,
        year
    FROM {{ ref('silver_google_maps_activities') }}
    WHERE location_name IS NOT NULL
),

location_aggregates AS (
    SELECT
        location_name,
        any(location_address) AS location_address,
        any(location_url) AS location_url,
        any(latitude) AS latitude,
        any(longitude) AS longitude,

        -- Visit counts
        COUNT(*) AS total_visits,
        COUNT(DISTINCT activity_date) AS unique_visit_days,
        COUNT(DISTINCT month_start) AS unique_visit_months,

        -- Temporal metrics
        MIN(activity_time) AS first_visit,
        MAX(activity_time) AS last_visit,
        dateDiff('day', MIN(activity_time), MAX(activity_time)) AS days_span,

        -- Visit patterns
        SUM(is_weekend) AS weekend_visits,
        COUNT(*) - SUM(is_weekend) AS weekday_visits,
        ROUND(SUM(is_weekend) * 100.0 / COUNT(*), 1) AS weekend_visit_pct,

        -- Time of day distribution
        countIf(time_of_day = 'Morning') AS morning_visits,
        countIf(time_of_day = 'Afternoon') AS afternoon_visits,
        countIf(time_of_day = 'Evening') AS evening_visits,
        countIf(time_of_day = 'Night') AS night_visits

    FROM location_visits
    GROUP BY location_name
),

ranked_locations AS (
    SELECT
        *,

        -- Most common time of day (determined after aggregation)
        CASE
            WHEN morning_visits >= afternoon_visits
                AND morning_visits >= evening_visits
                AND morning_visits >= night_visits
            THEN 'Morning'
            WHEN afternoon_visits >= evening_visits
                AND afternoon_visits >= night_visits
            THEN 'Afternoon'
            WHEN evening_visits >= night_visits
            THEN 'Evening'
            ELSE 'Night'
        END AS most_common_time_of_day,
        -- Calculate visits per month (avoid division by zero)
        CASE
            WHEN unique_visit_months > 0
            THEN ROUND(total_visits::Float64 / unique_visit_months, 2)
            ELSE total_visits::Float64
        END AS avg_visits_per_month,

        -- Calculate days between visits
        CASE
            WHEN total_visits > 1 AND days_span > 0
            THEN ROUND(days_span::Float64 / (total_visits - 1), 1)
            ELSE NULL
        END AS avg_days_between_visits,

        -- Ranking by total visits
        ROW_NUMBER() OVER (ORDER BY total_visits DESC) AS visit_rank,

        -- Recency score (1 = visited today, 0 = first visit was long ago)
        CASE
            WHEN dateDiff('day', first_visit, now()) > 0
            THEN ROUND(
                (dateDiff('day', first_visit, now()) - dateDiff('day', last_visit, now()))::Float64 /
                dateDiff('day', first_visit, now()),
                2
            )
            ELSE 1.0
        END AS recency_score

    FROM location_aggregates
)

SELECT
    location_name,
    location_address,
    location_url,
    latitude,
    longitude,

    -- Visit metrics
    total_visits,
    unique_visit_days,
    unique_visit_months,
    avg_visits_per_month,
    avg_days_between_visits,

    -- Temporal info
    first_visit,
    last_visit,
    days_span,
    dateDiff('day', last_visit, now()) AS days_since_last_visit,

    -- Visit patterns
    weekend_visits,
    weekday_visits,
    weekend_visit_pct,

    -- Time of day
    morning_visits,
    afternoon_visits,
    evening_visits,
    night_visits,
    most_common_time_of_day,

    -- Ranking and scoring
    visit_rank,
    recency_score,

    -- Classification
    CASE
        WHEN total_visits >= 50 THEN 'Very Frequent'
        WHEN total_visits >= 20 THEN 'Frequent'
        WHEN total_visits >= 10 THEN 'Regular'
        WHEN total_visits >= 5 THEN 'Occasional'
        ELSE 'Rare'
    END AS visit_frequency_category,

    CASE
        WHEN recency_score >= 0.8 THEN 'Current Favorite'
        WHEN recency_score >= 0.5 THEN 'Recent'
        WHEN recency_score >= 0.2 THEN 'Past Favorite'
        ELSE 'Historical'
    END AS recency_category

FROM ranked_locations
ORDER BY total_visits DESC
