{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    Silver Layer: YouTube Watch History

    Cleans and enriches raw YouTube watch history from bronze layer.
    - Removes duplicates based on activity_time and video URL
    - Adds temporal attributes (hour, day of week, etc.)
    - Extracts video ID from URL
    - Classifies activity types
    - Parses product and detail arrays
    - Filters out invalid data
*/

WITH raw_history AS (
    SELECT
        -- Activity details
        header,
        title,
        activity_time,
        activity_date,
        title_url,
        description,
        products,
        activity_controls,
        details,

        -- Export metadata
        export_timestamp,
        export_job_id,
        export_date,
        source,
        resource,
        record_count,
        dag_id,
        run_id,

        -- Deduplication: keep most recent export
        ROW_NUMBER() OVER (
            PARTITION BY activity_time, title_url
            ORDER BY export_timestamp DESC
        ) AS row_num

    FROM {{ ref('bronze_youtube_watch_history') }}
    WHERE
        -- Filter out invalid data
        activity_time IS NOT NULL
        AND title != ''
),

deduplicated AS (
    SELECT
        header,
        title,
        activity_time,
        activity_date,
        title_url,
        description,
        products,
        activity_controls,
        details,
        export_timestamp,
        export_job_id,
        export_date,
        source,
        resource,
        record_count,
        dag_id,
        run_id
    FROM raw_history
    WHERE row_num = 1
)

SELECT
    -- Generate a unique ID for each watch activity
    cityHash64(
        toString(activity_time) ||
        coalesce(title_url, '') ||
        coalesce(title, '')
    ) AS activity_id,

    -- Activity details
    header,
    title,
    activity_time,
    activity_date,
    title_url,
    description,

    -- Extract video ID from URL (format: https://www.youtube.com/watch?v=VIDEO_ID)
    extractURLParameter(title_url, 'v') AS video_id,

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

    -- Activity type classification (based on title and description)
    CASE
        WHEN title LIKE 'Watched%' THEN 'watched'
        WHEN title LIKE 'Searched for%' THEN 'search'
        WHEN title LIKE 'Visited%' THEN 'visit'
        WHEN title LIKE 'Subscribed to%' THEN 'subscribe'
        WHEN title LIKE 'Liked%' THEN 'like'
        WHEN title LIKE 'Commented on%' THEN 'comment'
        WHEN title LIKE 'Shared%' THEN 'share'
        ELSE 'other'
    END AS activity_type,

    -- Parse products array
    products,
    arrayStringConcat(products, ', ') AS products_list,

    -- Parse activity controls array
    activity_controls,
    arrayStringConcat(activity_controls, ', ') AS activity_controls_list,

    -- Parse details array (e.g., "From Google Ads")
    details,
    arrayStringConcat(details, ', ') AS details_list,

    -- Check if video was from ads
    CASE
        WHEN arrayStringConcat(details, ', ') LIKE '%From Google Ads%' THEN 1
        ELSE 0
    END AS is_from_ads,

    -- Export metadata
    export_timestamp,
    export_job_id,
    export_date,
    source,
    resource,
    record_count,
    dag_id,
    run_id

FROM deduplicated
