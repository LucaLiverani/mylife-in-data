{{
    config(
        materialized='view',
        schema='silver'
    )
}}

/*
    Silver Layer: Spotify Artists

    Provides the latest version of each artist's details.
    - Deduplicates by artist_id
    - Keeps most recently ingested data
*/

WITH raw_artists AS (
    SELECT
        artist_id,
        artist_name,
        artist_uri,
        artist_type,
        popularity,
        followers_total,
        genres,
        image_url,
        external_url_spotify,
        ingested_at,
        execution_date,
        dag_id,
        run_id,
        source,
        batch_number,

        -- Keep most recent version of each artist
        ROW_NUMBER() OVER (
            PARTITION BY artist_id
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM {{ ref('bronze_spotify_artists') }}
    WHERE
        artist_id != ''
        AND artist_name != ''
)

SELECT
    artist_id,
    artist_name,
    artist_uri,
    artist_type,
    popularity,
    followers_total,
    genres,
    image_url,
    external_url_spotify,
    ingested_at AS last_updated,
    source

FROM raw_artists
WHERE row_num = 1
