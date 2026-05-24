-- One row of cross-source totals for the home page.
-- Phase 3: Spotify columns only; youtube/maps default to 0 until those
-- pipelines come online in Phase 5/6 (this model gets replaced then).

{{ config(materialized='view', schema='gold') }}

SELECT
    (SELECT uniqExact(track_id) FROM {{ ref('silver_spotify_plays') }})            AS songsStreamed,
    (SELECT uniqExact(primary_artist_id) FROM {{ ref('silver_spotify_plays') }})   AS artistsListened,
    toUInt64(0)                                                                    AS videosWatched,
    toUInt64(0)                                                                    AS youtubeChannels,
    toUInt64(0)                                                                    AS searchQueries,
    toUInt64(0)                                                                    AS citiesVisited
