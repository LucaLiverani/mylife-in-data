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
        -- Filter out invalid data
        activity_time IS NOT NULL
        AND location_name != ''
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
    latitude,
    longitude,

    -- Location validity
    CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1
        ELSE 0
    END AS has_coordinates,

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
