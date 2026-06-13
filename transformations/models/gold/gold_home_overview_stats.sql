-- One row of cross-source totals for the home page.
-- Maps metrics come from the activity-based silver model (the legacy Timeline
-- bronze tables were removed when Maps Timeline moved on-device in 2024).
-- searchQueries combines YouTube + Maps search activity.

{{ config(materialized='view', schema='gold') }}

-- Every subquery is floored to the shared kpi_start_date (on its own source's
-- timestamp column) so the home totals span the same window as the per-source
-- KPI cards.
SELECT
    (SELECT uniqExact(track_id) FROM {{ ref('silver_spotify_plays_merged') }}
        WHERE played_at >= toDateTime('{{ var("kpi_start_date") }}'))              AS songsStreamed,
    (SELECT uniqExact(primary_artist_id) FROM {{ ref('silver_spotify_plays_merged') }}
        WHERE primary_artist_id != ''
          AND played_at >= toDateTime('{{ var("kpi_start_date") }}'))             AS artistsListened,
    -- Read the deduped silver views (not raw bronze.youtube_*): overlapping
    -- Takeout + live imports leave duplicate rows in bronze, which counting
    -- without FINAL inflated (~21k vs the true ~12k). Silver matches the
    -- YouTube page so home and per-source KPIs agree.
    (SELECT count() FROM {{ ref('silver_youtube_watches') }}
        WHERE watched_date >= toDate('{{ var("kpi_start_date") }}'))             AS videosWatched,
    (SELECT uniqExact(channel_id) FROM {{ ref('silver_youtube_watches') }}
        WHERE channel_id != ''
          AND watched_date >= toDate('{{ var("kpi_start_date") }}'))            AS youtubeChannels,
    (SELECT count() FROM {{ ref('silver_youtube_searches') }}
        WHERE searched_date >= toDate('{{ var("kpi_start_date") }}'))
      + (SELECT countIf(activity_type = 'search')
         FROM {{ ref('silver_maps_activity_enriched') }}
         WHERE is_private = 0
           AND event_date >= toDate('{{ var("kpi_start_date") }}'))              AS searchQueries,
    -- "Cities" = the Maps page's strict definition (localities you actually
    -- NAVIGATED to, not every distinct locality) so home and /maps agree. Read
    -- straight from the maps KPI view — one source of truth, already floored.
    (SELECT cities_visited FROM {{ ref('gold_maps_kpis_dashboard') }})            AS citiesVisited,
    -- Hours for the Home channel strips. YouTube is the count×duration proxy
    -- (0 until the enricher fills durations).
    round((SELECT sum(duration_ms) FROM {{ ref('silver_spotify_plays_merged') }}
        WHERE played_at >= toDateTime('{{ var("kpi_start_date") }}')) / 3600000.0, 1) AS spotifyHours,
    round((SELECT sum(duration_seconds) FROM {{ ref('silver_youtube_watches') }}
        WHERE watched_date >= toDate('{{ var("kpi_start_date") }}')) / 3600.0, 1) AS youtubeHours
