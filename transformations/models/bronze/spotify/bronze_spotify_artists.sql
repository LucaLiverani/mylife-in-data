{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    Bronze Layer: Spotify Artists

    Raw artist enrichment data from MinIO S3 bucket.
    Reads JSONL files from inbound/raw/spotify/api/artists/

    Data structure:
    - raw_artist: Artist details from Spotify API
    - _ingestion_metadata: Airflow ingestion metadata
    - Includes genres, popularity, followers, images
*/

SELECT
    -- Artist identification
    JSONExtractString(raw_json, 'raw_artist', 'id') AS artist_id,
    JSONExtractString(raw_json, 'raw_artist', 'name') AS artist_name,
    JSONExtractString(raw_json, 'raw_artist', 'uri') AS artist_uri,
    JSONExtractString(raw_json, 'raw_artist', 'type') AS artist_type,

    -- Popularity metrics
    JSONExtractInt(raw_json, 'raw_artist', 'popularity') AS popularity,
    JSONExtractInt(raw_json, 'raw_artist', 'followers', 'total') AS followers_total,

    -- Genres (array)
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'genres')) AS genres,

    -- Images (extract first image URL if available)
    JSONExtractString(raw_json, 'raw_artist', 'images', 1, 'url') AS image_url,
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_artist', 'images')) AS images_raw,

    -- External links
    JSONExtractString(raw_json, 'raw_artist', 'external_urls', 'spotify') AS external_url_spotify,

    -- Ingestion metadata
    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    JSONExtractString(raw_json, '_ingestion_metadata', 'logical_date') AS execution_date,
    JSONExtractString(raw_json, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'source') AS source,
    JSONExtractInt(raw_json, '_ingestion_metadata', 'batch_number') AS batch_number,

    -- Keep raw JSON for reference
    raw_json

FROM s3(
    'http://minio:9000/inbound/raw/spotify/api/artists/*.jsonl',
    'admin',
    'minio08062013',
    'LineAsString',
    'raw_json String'
)
WHERE JSONExtractString(raw_json, 'raw_artist', 'id') != ''
ORDER BY ingested_at DESC
