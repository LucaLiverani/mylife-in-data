{{
    config(
        materialized='table',
        schema='gold'
    )
}}

/*
    Gold Layer: Recent Maps Activities

    Provides a clean view of recent Google Maps activities for dashboard display.
    Includes all activities (with or without coordinates) to show complete activity history.

    Dashboard Use:
    - Recent activity timeline widget
    - Activity feed display
    - Last actions overview
*/

SELECT
    activity_id,
    toString(activity_time) AS time,
    COALESCE(NULLIF(title, ''), 'Unknown activity') AS location,
    activity_type AS type,
    time_of_day AS timeOfDay,
    activity_time AS activity_time_raw  -- Keep original for ordering

FROM {{ ref('silver_google_maps_activities') }}
ORDER BY activity_time DESC
