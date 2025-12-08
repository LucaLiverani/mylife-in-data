{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Spotify KPIs Dashboard View

    Pre-formatted view of gold_spotify_kpis optimized for dashboard consumption.
    All fields renamed to match dashboard API expectations.

    Dashboard Use:
    - Simple SELECT * query
    - All columns match dashboard field names
*/

SELECT
    -- Renamed columns for /api/spotify/data
    total_plays_raw AS songs_streamed,
    unique_artists_raw AS unique_artists,
    total_time,
    avg_daily

FROM {{ ref('gold_spotify_kpis') }}
