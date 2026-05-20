{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    Bronze Layer: Spotify Tracks

    Raw Spotify listening history from MinIO S3 bucket.
    Reads JSONL.gz files from inbound/raw/spotify/api/tracks/

    Data structure:
    - raw_item: Original Spotify API response
    - _ingestion_metadata: Airflow ingestion metadata
*/

SELECT
    -- Track information
    JSONExtractString(raw_json, 'raw_item', 'track', 'id') AS track_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'name') AS track_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'uri') AS track_uri,
    JSONExtractInt(raw_json, 'raw_item', 'track', 'popularity') AS track_popularity,
    JSONExtractInt(raw_json, 'raw_item', 'track', 'duration_ms') AS track_duration_ms,
    JSONExtractBool(raw_json, 'raw_item', 'track', 'explicit') AS track_explicit,
    JSONExtractString(raw_json, 'raw_item', 'track', 'preview_url') AS track_preview_url,
    JSONExtractString(raw_json, 'raw_item', 'track', 'external_ids', 'isrc') AS isrc,

    -- Album information
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'id') AS album_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'name') AS album_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'album_type') AS album_type,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'release_date') AS album_release_date,
    JSONExtractString(raw_json, 'raw_item', 'track', 'album', 'uri') AS album_uri,

    -- Primary artist (first in array)
    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'id') AS artist_id,
    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'name') AS artist_name,
    JSONExtractString(raw_json, 'raw_item', 'track', 'artists', 1, 'uri') AS artist_uri,

    -- All artists (arrays for multi-artist tracks)
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'raw_item', 'track', 'artists')) AS artists_raw,

    -- Context (where it was played)
    JSONExtractString(raw_json, 'raw_item', 'context', 'type') AS context_type,
    JSONExtractString(raw_json, 'raw_item', 'context', 'uri') AS context_uri,

    -- Playback timestamp
    parseDateTime64BestEffort(JSONExtractString(raw_json, 'raw_item', 'played_at')) AS played_at,

    -- Ingestion metadata
    parseDateTime64BestEffort(JSONExtractString(raw_json, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    JSONExtractString(raw_json, '_ingestion_metadata', 'logical_date') AS execution_date,
    JSONExtractString(raw_json, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(raw_json, '_ingestion_metadata', 'source') AS source,

    -- Keep raw JSON for reference
    raw_json

FROM s3(
    'http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz',
    'admin',
    'minio08062013',
    'LineAsString',
    'raw_json String'
)
WHERE JSONExtractString(raw_json, 'raw_item', 'track', 'id') != ''
ORDER BY played_at DESC
