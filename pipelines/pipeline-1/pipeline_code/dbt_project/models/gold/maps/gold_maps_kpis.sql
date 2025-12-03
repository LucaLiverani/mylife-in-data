{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Maps KPIs

    Single row with key performance indicators for Google Maps usage.
    Dashboard KPI cards.
*/

SELECT
    -- Activity counts
    count() AS total_activities,
    countIf(activity_type = 'directions') AS total_directions,
    countIf(activity_type = 'search') AS total_searches,
    countIf(activity_type = 'explore') AS total_explorations,
    countIf(likely_visit = 1) AS total_likely_visits,

    -- Unique metrics
    uniq(toDate(activity_time)) AS days_with_activity,
    uniq(location_name) AS unique_locations,
    uniqIf(replaceRegexpOne(title, '^Directions to ', ''), activity_type = 'directions') AS unique_destinations,

    -- Temporal
    min(activity_date) AS first_activity,
    max(activity_date) AS last_activity,
    dateDiff('day', min(activity_date), max(activity_date)) AS days_tracked,

    -- Averages
    round(count() / uniq(toDate(activity_time)), 2) AS avg_activities_per_day,
    round(countIf(activity_type = 'directions') / uniq(toDate(activity_time)), 2) AS avg_directions_per_day,
    round(countIf(activity_type = 'search') / uniq(toDate(activity_time)), 2) AS avg_searches_per_day,

    -- Percentages
    round(countIf(activity_type = 'directions') / count() * 100, 1) AS directions_pct,
    round(countIf(activity_type = 'search') / count() * 100, 1) AS search_pct,
    round(countIf(activity_type = 'explore') / count() * 100, 1) AS explore_pct,
    round(countIf(likely_visit = 1) / count() * 100, 1) AS visit_rate_pct,

    -- Top destination (most frequent)
    any(replaceRegexpOne(title, '^Directions to ', '')) AS sample_top_destination,

    -- Metadata
    now() AS updated_at

FROM {{ ref('silver_google_maps_activities') }}
