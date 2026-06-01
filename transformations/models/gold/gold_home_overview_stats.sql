-- One row of cross-source totals for the home page.
-- Maps metrics come from the activity-based silver model (the Timeline-era
-- bronze.maps_visits / bronze.maps_search tables are empty post-pivot).
-- searchQueries combines YouTube + Maps search activity.

{{ config(materialized='view', schema='gold') }}

-- Every subquery is floored to the shared kpi_start_date (on its own source's
-- timestamp column) so the home totals span the same window as the per-source
-- KPI cards.
SELECT
    (SELECT uniqExact(track_id) FROM {{ ref('silver_spotify_plays') }}
        WHERE played_at >= toDateTime('{{ var("kpi_start_date") }}'))              AS songsStreamed,
    (SELECT uniqExact(primary_artist_id) FROM {{ ref('silver_spotify_plays') }}
        WHERE primary_artist_id != ''
          AND played_at >= toDateTime('{{ var("kpi_start_date") }}'))             AS artistsListened,
    (SELECT count() FROM {{ source('bronze', 'youtube_watch_history') }}
        WHERE watched_at >= toDateTime('{{ var("kpi_start_date") }}'))            AS videosWatched,
    (SELECT uniqExact(channel_id) FROM {{ source('bronze', 'youtube_watch_history') }}
        WHERE channel_id != ''
          AND watched_at >= toDateTime('{{ var("kpi_start_date") }}'))           AS youtubeChannels,
    (SELECT count() FROM {{ source('bronze', 'youtube_search_history') }}
        WHERE searched_at >= toDateTime('{{ var("kpi_start_date") }}'))
      + (SELECT countIf(activity_type = 'search')
         FROM {{ ref('silver_maps_activity_enriched') }}
         WHERE is_private = 0
           AND event_date >= toDate('{{ var("kpi_start_date") }}'))              AS searchQueries,
    -- "Cities" = distinct enriched localities from Maps activity. Populates as
    -- maps_place_enrichment fills bronze.maps_place_catalog (locality column).
    (SELECT uniqExactIf(locality, locality != '')
     FROM {{ ref('silver_maps_activity_enriched') }}
     WHERE is_private = 0
       AND event_date >= toDate('{{ var("kpi_start_date") }}'))                  AS citiesVisited,
    -- Hours for the Home channel strips. YouTube is the count×duration proxy
    -- (0 until the enricher fills durations).
    round((SELECT sum(duration_ms) FROM {{ ref('silver_spotify_plays') }}
        WHERE played_at >= toDateTime('{{ var("kpi_start_date") }}')) / 3600000.0, 1) AS spotifyHours,
    round((SELECT sum(duration_seconds) FROM {{ ref('silver_youtube_watches') }}
        WHERE watched_date >= toDate('{{ var("kpi_start_date") }}')) / 3600.0, 1) AS youtubeHours
