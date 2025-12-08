{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    Bronze Layer: YouTube Watch History

    Raw YouTube watch history from MinIO S3 bucket.
    Reads JSONL.gz files from inbound/raw/google/youtube/

    Data structure:
    - activity: YouTube video watch activity (title, URL, time, description)
    - _export_metadata: Google Data Portability API export metadata
*/

SELECT
    -- Activity details
    JSONExtractString(raw_json, 'activity', 'header') AS header,
    JSONExtractString(raw_json, 'activity', 'title') AS title,
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'activity', 'time')) AS activity_time,
    toDate(parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'activity', 'time'))) AS activity_date,
    JSONExtractString(raw_json, 'activity', 'titleUrl') AS title_url,
    JSONExtractString(raw_json, 'activity', 'description') AS description,

    -- Products and activity controls
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'products')) AS products,
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'activityControls')) AS activity_controls,

    -- Details array (e.g., "From Google Ads")
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'details')) AS details,

    -- Export metadata
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, '_export_metadata', 'export_timestamp')) AS export_timestamp,
    JSONExtractString(raw_json, '_export_metadata', 'export_job_id') AS export_job_id,
    toDate(JSONExtractString(raw_json, '_export_metadata', 'export_date')) AS export_date,
    JSONExtractString(raw_json, '_export_metadata', 'source') AS source,
    JSONExtractString(raw_json, '_export_metadata', 'resource') AS resource,
    JSONExtractUInt(raw_json, '_export_metadata', 'record_count') AS record_count,
    JSONExtractString(raw_json, '_export_metadata', 'dag_id') AS dag_id,
    JSONExtractString(raw_json, '_export_metadata', 'run_id') AS run_id,

    -- Keep raw JSON for reference
    raw_json

FROM s3(
    'http://minio:9000/inbound/raw/google/youtube/*.jsonl.gz',
    'admin',
    'minio08062013',
    'LineAsString',
    'raw_json String'
)
WHERE activity_time IS NOT NULL  -- Only keep records with valid timestamps
ORDER BY activity_time DESC
