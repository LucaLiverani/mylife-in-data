-- One row of cross-source totals for the home page.
-- Maps metrics come from the activity-based silver model (the Timeline-era
-- bronze.maps_visits / bronze.maps_search tables are empty post-pivot).
-- searchQueries combines YouTube + Maps search activity.

{{ config(materialized='view', schema='gold') }}

SELECT
    (SELECT uniqExact(track_id) FROM {{ ref('silver_spotify_plays') }})            AS songsStreamed,
    (SELECT uniqExact(primary_artist_id) FROM {{ ref('silver_spotify_plays') }}
        WHERE primary_artist_id != '')                                             AS artistsListened,
    (SELECT count() FROM {{ source('bronze', 'youtube_watch_history') }})          AS videosWatched,
    (SELECT uniqExact(channel_id) FROM {{ source('bronze', 'youtube_watch_history') }}
        WHERE channel_id != '')                                                    AS youtubeChannels,
    (SELECT count() FROM {{ source('bronze', 'youtube_search_history') }})
      + (SELECT countIf(activity_type = 'search')
         FROM {{ ref('silver_maps_activity_enriched') }} WHERE is_private = 0)      AS searchQueries,
    -- "Cities" = distinct enriched localities from Maps activity. Populates as
    -- maps_place_enrichment fills bronze.maps_place_catalog (locality column).
    (SELECT uniqExactIf(locality, locality != '')
     FROM {{ ref('silver_maps_activity_enriched') }} WHERE is_private = 0)          AS citiesVisited
