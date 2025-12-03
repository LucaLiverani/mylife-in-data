{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Top Destinations

    Most frequently requested directions and searched places.
    Helps identify your regular destinations.

    Dashboard Use:
    - Top 20 destinations bar chart
    - Destination frequency heatmap
    - Home/Work/Frequent places identification
*/

WITH direction_activities AS (
    SELECT
        -- Extract destination from title
        replaceRegexpOne(title, '^Directions to ', '') AS destination,
        activity_type,
        location_name,
        latitude,
        longitude,
        activity_time,
        likely_visit
    FROM {{ ref('silver_google_maps_activities') }}
    WHERE activity_type IN ('directions', 'search')
        AND title != ''
),

destination_summary AS (
    SELECT
        destination,
        activity_type,

        -- Aggregate metrics
        count() AS request_count,
        countIf(likely_visit = 1) AS likely_visit_count,
        uniq(toDate(activity_time)) AS unique_days,

        -- Temporal
        min(activity_time) AS first_request,
        max(activity_time) AS last_request,
        dateDiff('day', min(activity_time), max(activity_time)) AS days_span,

        -- Location (use most common coordinates for this destination)
        any(latitude) AS latitude,
        any(longitude) AS longitude,

        -- Frequency metrics
        round(count() / uniq(toDate(activity_time)), 2) AS avg_requests_per_day,
        dateDiff('day', max(activity_time), today()) AS days_since_last_request

    FROM direction_activities
    GROUP BY destination, activity_type
)

SELECT
    destination,
    activity_type,
    request_count,
    likely_visit_count,
    unique_days,
    first_request,
    last_request,
    days_span,
    latitude,
    longitude,
    avg_requests_per_day,
    days_since_last_request,

    -- Ranking
    ROW_NUMBER() OVER (PARTITION BY activity_type ORDER BY request_count DESC) AS rank_within_type,
    ROW_NUMBER() OVER (ORDER BY request_count DESC) AS overall_rank,

    -- Categorization heuristics
    CASE
        WHEN request_count >= 50 THEN 'Very Frequent'
        WHEN request_count >= 20 THEN 'Frequent'
        WHEN request_count >= 10 THEN 'Regular'
        WHEN request_count >= 5 THEN 'Occasional'
        ELSE 'Rare'
    END AS frequency_category,

    CASE
        WHEN days_since_last_request <= 7 THEN 'Recent'
        WHEN days_since_last_request <= 30 THEN 'Current'
        WHEN days_since_last_request <= 90 THEN 'Past Quarter'
        ELSE 'Historical'
    END AS recency_category

FROM destination_summary
WHERE request_count >= 3  -- Filter out one-off destinations
ORDER BY request_count DESC
LIMIT 100
