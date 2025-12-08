{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: YouTube KPIs Dashboard View

    Pre-formatted view of gold_youtube_kpis optimized for dashboard consumption.
    All fields renamed to match dashboard API expectations.

    Dashboard Use:
    - Simple SELECT * query
    - All columns match dashboard field names
*/

SELECT
    -- Renamed columns for /api/youtube/data
    total_videos_raw AS total_videos,
    avg_daily

FROM {{ ref('gold_youtube_kpis') }}
