{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Activity Types Dashboard View

    Pre-formatted view of activity type breakdown for dashboard charts.
    Shows distribution of different YouTube interaction types.

    Dashboard Use:
    - Simple SELECT * query
    - Category distribution chart
    - Activity type breakdown visualization
*/

SELECT
    display_name AS name,
    percentage AS value,
    activity_count,
    activity_type

FROM {{ ref('gold_youtube_activity_type_breakdown') }}
ORDER BY rank
