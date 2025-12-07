{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Activity Breakdown by Type

    Aggregates daily Google Maps activities by activity type for trend analysis.
    Includes:
    - Daily counts for each activity type (directions, searches, explorations, etc.)
    - Total daily activities
    - Percentage breakdown by type

    Dashboard Use:
    - Stacked area chart showing activity trends over time
    - Activity type distribution analysis
*/

WITH daily_breakdown AS (
    SELECT
        activity_date,

        -- Activity type counts
        countIf(activity_type = 'directions') AS directions,
        countIf(activity_type = 'search') AS searches,
        countIf(activity_type = 'explore') AS explorations,
        countIf(activity_type = 'place_view') AS place_views,
        countIf(activity_type = 'app_usage') AS app_usage,
        countIf(activity_type = 'view') AS views,
        countIf(activity_type = 'review') AS reviews,
        countIf(activity_type = 'save') AS saves,
        countIf(activity_type NOT IN ('directions', 'search', 'explore', 'place_view', 'app_usage', 'view', 'review', 'save')) AS other,

        -- Total daily activities
        count(*) AS total_activities

    FROM {{ ref('silver_google_maps_activities') }}
    GROUP BY activity_date
)

SELECT
    activity_date,

    -- Individual activity type counts
    directions,
    searches,
    explorations,
    place_views,
    app_usage,
    views,
    reviews,
    saves,
    other,

    -- Total
    total_activities,

    -- Percentages
    round(directions * 100.0 / total_activities, 1) AS directions_pct,
    round(searches * 100.0 / total_activities, 1) AS searches_pct,
    round(explorations * 100.0 / total_activities, 1) AS explorations_pct,
    round(place_views * 100.0 / total_activities, 1) AS place_views_pct,
    round(other * 100.0 / total_activities, 1) AS other_pct,

    -- Day metadata
    toDayOfWeek(activity_date) AS day_of_week,
    dateName('weekday', activity_date) AS day_name,
    CASE WHEN toDayOfWeek(activity_date) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend,

    -- Running totals
    sum(total_activities) OVER (ORDER BY activity_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_activities,
    sum(directions) OVER (ORDER BY activity_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_directions,

    -- Moving averages (7-day)
    avg(total_activities) OVER (ORDER BY activity_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_total_activities,
    avg(directions) OVER (ORDER BY activity_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_directions,
    avg(searches) OVER (ORDER BY activity_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7_searches

FROM daily_breakdown
ORDER BY activity_date DESC
