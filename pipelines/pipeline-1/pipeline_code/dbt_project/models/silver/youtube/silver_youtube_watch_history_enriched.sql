{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    Silver Layer: YouTube Watch History Enriched

    Enriches YouTube watch history with video metadata from YouTube Data API v3.
    - Joins watch history with video metadata (channel, duration, category, stats)
    - Adds channel information for each watched video
    - Includes video statistics and categorization
    - Maintains all records even if metadata is not available (LEFT JOIN)
*/

SELECT
    -- Activity identification
    wh.activity_id,

    -- Activity details
    wh.header,
    wh.title,
    wh.activity_time,
    wh.activity_date,
    wh.title_url,
    wh.description,
    wh.video_id,

    -- Temporal attributes
    wh.activity_hour,
    wh.day_of_week,
    wh.day_name,
    wh.week_start,
    wh.month_start,
    wh.year,
    wh.month,
    wh.quarter,
    wh.time_of_day,
    wh.is_weekend,

    -- Activity classification
    wh.activity_type,
    wh.is_from_ads,

    -- Products and controls
    wh.products,
    wh.products_list,
    wh.activity_controls,
    wh.activity_controls_list,
    wh.details,
    wh.details_list,

    -- Enriched metadata from YouTube API
    vm.channel_id,
    vm.channel_title,
    vm.duration_seconds,
    vm.category_id,
    vm.category_name,
    vm.view_count,
    vm.like_count,
    vm.comment_count,
    vm.published_at AS video_published_at,
    vm.published_date AS video_published_date,

    -- Duration formatting helpers
    CASE
        WHEN vm.duration_seconds IS NOT NULL THEN
            concat(
                toString(intDiv(vm.duration_seconds, 3600)), ':',
                leftPad(toString(intDiv(vm.duration_seconds % 3600, 60)), 2, '0'), ':',
                leftPad(toString(vm.duration_seconds % 60), 2, '0')
            )
        ELSE NULL
    END AS duration_formatted,

    -- Duration classification
    CASE
        WHEN vm.duration_seconds IS NULL THEN 'unknown'
        WHEN vm.duration_seconds < 60 THEN 'shorts'  -- Under 1 minute (YouTube Shorts)
        WHEN vm.duration_seconds < 300 THEN 'short'  -- 1-5 minutes
        WHEN vm.duration_seconds < 1200 THEN 'medium'  -- 5-20 minutes
        WHEN vm.duration_seconds < 3600 THEN 'long'  -- 20-60 minutes
        ELSE 'very_long'  -- Over 1 hour
    END AS duration_category,

    -- Engagement metrics (only for watched videos)
    CASE
        WHEN wh.activity_type = 'watched' AND vm.view_count > 0 THEN
            round(vm.like_count / vm.view_count * 100, 2)
        ELSE NULL
    END AS like_rate_percent,

    CASE
        WHEN wh.activity_type = 'watched' AND vm.view_count > 0 THEN
            round(vm.comment_count / vm.view_count * 100, 2)
        ELSE NULL
    END AS comment_rate_percent,

    -- Flags
    CASE
        WHEN vm.video_id IS NOT NULL THEN 1
        ELSE 0
    END AS is_enriched,

    vm.enriched_at AS metadata_enriched_at,

    -- Export metadata
    wh.export_timestamp,
    wh.export_job_id,
    wh.export_date,
    wh.source,
    wh.resource,
    wh.record_count,
    wh.dag_id,
    wh.run_id

FROM {{ ref('silver_youtube_watch_history') }} AS wh
LEFT JOIN {{ ref('bronze_youtube_video_metadata') }} AS vm
    ON wh.video_id = vm.video_id
