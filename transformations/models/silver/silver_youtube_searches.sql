-- Cleanup of search history — passthrough today.

{{ config(materialized='view', schema='silver') }}

SELECT
    searched_at,
    query,
    toDate(searched_at)                AS searched_date
FROM {{ source('bronze', 'youtube_search_history') }} FINAL
