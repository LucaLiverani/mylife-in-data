{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Daily Activity Dashboard View (Last 30 Days)

    Pre-filtered and formatted view of daily activity breakdown for dashboard charts.
    Shows only the last 30 days with consolidated 'other' category.

    Dashboard Use:
    - Simple SELECT * query
    - Date formatted as string
    - 'Other' category pre-computed
    - Last 30 days only
*/

SELECT
    -- Date formatted as string
    toString(activity_date) AS date,

    -- Main activity types
    directions,
    searches,
    explorations,

    -- Consolidated 'other' category
    place_views + app_usage + views + reviews + saves + other AS other,

    -- Keep raw date for filtering (if needed)
    activity_date

FROM {{ ref('gold_maps_daily_activity_breakdown') }}
WHERE activity_date >= today() - 30
ORDER BY activity_date ASC
