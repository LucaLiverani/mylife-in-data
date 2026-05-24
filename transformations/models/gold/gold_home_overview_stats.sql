-- One row of cross-source totals for the home page.
-- Phase 6: Spotify + YouTube + Maps columns. citiesVisited derived from
-- bronze.maps_visits; searchQueries combines YouTube + Maps search.

{{ config(materialized='view', schema='gold') }}

SELECT
    (SELECT uniqExact(track_id) FROM {{ ref('silver_spotify_plays') }})            AS songsStreamed,
    (SELECT uniqExact(primary_artist_id) FROM {{ ref('silver_spotify_plays') }})   AS artistsListened,
    (SELECT count() FROM {{ source('bronze', 'youtube_watch_history') }})          AS videosWatched,
    (SELECT uniqExact(channel_id) FROM {{ source('bronze', 'youtube_watch_history') }}
        WHERE channel_id != '')                                                    AS youtubeChannels,
    (SELECT count() FROM {{ source('bronze', 'youtube_search_history') }})
      + (SELECT count() FROM {{ source('bronze', 'maps_search') }})                AS searchQueries,
    (SELECT uniqExact(place_name) FROM {{ source('bronze', 'maps_visits') }}
        WHERE place_name != '')                                                    AS citiesVisited
