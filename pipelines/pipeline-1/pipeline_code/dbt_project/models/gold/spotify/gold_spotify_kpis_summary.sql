{{
    config(
        materialized='view',
        schema='gold'
    )
}}

/*
    Gold Layer: Spotify KPIs Summary View

    Pre-formatted view for /api/spotify/summary endpoint.
    All fields renamed to match summary API expectations.

    Dashboard Use:
    - Simple SELECT * query for summary stats
*/

SELECT
    unique_artists_raw AS artists,
    total_plays_raw AS songs,
    total_time AS total_hours

FROM {{ ref('gold_spotify_kpis') }}
