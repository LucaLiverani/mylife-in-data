{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    Silver Layer: Google Maps Activities

    Cleans and enriches raw Google Maps activity data.
    - Removes duplicates based on activity_time and location
    - Adds temporal attributes (hour, day of week, etc.)
    - Extracts and parses product arrays
    - Filters out invalid data
    - Adds derived location attributes
*/

WITH raw_activities AS (
    SELECT
        -- Activity details
        header,
        title,
        activity_time,
        activity_date,
        products,
        activity_controls,

        -- Location details
        location_name,
        location_url,
        location_source_url,
        location_address,
        location_source,
        latitude,
        longitude,

        -- Export metadata
        export_timestamp,
        export_job_id,
        export_date,
        source,
        resource,

        -- Deduplication: keep most recent export
        ROW_NUMBER() OVER (
            PARTITION BY activity_time, location_name
            ORDER BY export_timestamp DESC
        ) AS row_num

    FROM {{ ref('bronze_google_maps_activities') }}
    WHERE
        -- Filter out invalid data (keep all activities, even without specific location)
        activity_time IS NOT NULL
),

deduplicated AS (
    SELECT
        header,
        title,
        activity_time,
        activity_date,
        products,
        activity_controls,
        location_name,
        location_url,
        location_source_url,
        location_address,
        location_source,
        latitude,
        longitude,
        export_timestamp,
        export_job_id,
        export_date,
        source,
        resource
    FROM raw_activities
    WHERE row_num = 1
)

SELECT
    -- Generate a unique ID for each activity
    cityHash64(
        toString(activity_time) ||
        coalesce(location_name, '') ||
        coalesce(toString(latitude), '') ||
        coalesce(toString(longitude), '')
    ) AS activity_id,

    -- Activity details
    header,
    title,
    activity_time,
    activity_date,

    -- Temporal attributes
    toHour(activity_time) AS activity_hour,
    toDayOfWeek(activity_time) AS day_of_week,
    dateName('weekday', activity_time) AS day_name,
    toStartOfWeek(activity_time) AS week_start,
    toStartOfMonth(activity_time) AS month_start,
    toYear(activity_time) AS year,
    toMonth(activity_time) AS month,
    toQuarter(activity_time) AS quarter,

    -- Time of day classification
    CASE
        WHEN toHour(activity_time) >= 5 AND toHour(activity_time) < 12 THEN 'Morning'
        WHEN toHour(activity_time) >= 12 AND toHour(activity_time) < 17 THEN 'Afternoon'
        WHEN toHour(activity_time) >= 17 AND toHour(activity_time) < 21 THEN 'Evening'
        ELSE 'Night'
    END AS time_of_day,

    -- Weekend flag
    CASE
        WHEN toDayOfWeek(activity_time) IN (6, 7) THEN 1
        ELSE 0
    END AS is_weekend,

    -- Location details
    location_name,
    location_url,
    location_source_url,
    location_address,
    location_source,
    latitude,
    longitude,

    -- Location validity
    CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1
        ELSE 0
    END AS has_coordinates,

    -- Activity type classification (based on title pattern)
    CASE
        -- Map interactions
        WHEN title = 'Explored on Google Maps' THEN 'explore'
        WHEN title = 'Used Maps' THEN 'app_usage'
        WHEN title LIKE 'Opened My Maps map:%' THEN 'custom_map'

        -- Search and navigation
        WHEN title LIKE 'Searched for%' THEN 'search'
        WHEN title LIKE 'Directions to%' THEN 'directions'
        WHEN title LIKE 'Viewed%' THEN 'view'

        -- User contributions
        WHEN title LIKE 'Reviewed%' THEN 'review'
        WHEN title LIKE 'Saved%' THEN 'save'
        WHEN title LIKE 'Added photo%' THEN 'photo'
        WHEN title LIKE 'Edited%' THEN 'edit'
        WHEN title LIKE 'Contributed%' THEN 'contribution'

        -- Notifications and system
        WHEN title LIKE '%notification%' THEN 'notification'

        -- Direct place names (no action prefix) - likely just viewed/browsed
        WHEN title != '' AND title NOT LIKE '%:%' AND title NOT LIKE 'Searched%'
             AND title NOT LIKE 'Directions%' THEN 'place_view'

        ELSE 'other'
    END AS activity_type,

    -- Likely visit indicator (heuristic based on multiple factors)
    CASE
        -- Definite visits (high confidence)
        WHEN title LIKE 'Reviewed%' OR title LIKE 'Added photo%' THEN 1  -- Reviewed/added photo = definitely visited
        WHEN location_source LIKE '%your places (Home)%' OR location_source LIKE '%your places (Work)%' THEN 1  -- Home/Work = visited

        -- Probable visits (medium confidence)
        WHEN title LIKE 'Directions to%' AND location_source LIKE '%your device%' THEN 1  -- Got directions + device location = likely visited

        -- Unlikely visits (low confidence)
        WHEN title LIKE 'Searched for%' THEN 0  -- Just searched, didn't visit
        WHEN title LIKE 'Directions to%' THEN 0  -- Got directions only = maybe visited
        WHEN title = 'Explored on Google Maps' THEN 0  -- Just browsing
        WHEN title = 'Used Maps' THEN 0  -- General app usage
        WHEN title LIKE 'Opened My Maps map:%' THEN 0  -- Viewing custom map

        -- Unknown/ambiguous
        ELSE 0
    END AS likely_visit,

    -- Products (keep as array for now)
    products,
    arrayStringConcat(products, ', ') AS products_list,

    -- Activity controls
    activity_controls,

    -- Export metadata
    export_timestamp,
    export_job_id,
    export_date,
    source,
    resource

FROM deduplicated
