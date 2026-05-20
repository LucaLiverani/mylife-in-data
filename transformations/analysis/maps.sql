-- Google Maps Data from MinIO S3 Bucket
-- Queries and unpacks JSONL.gz files from the inbound/raw/google/maps/ path
WITH raw_json AS (
    SELECT
        -- Activity details
        JSONExtractString(raw_json, 'activity', 'header') AS header,
        JSONExtractString(raw_json, 'activity', 'title') AS title,
        parseDateTime64BestEffort(JSONExtractString(raw_json, 'activity', 'time')) AS activity_time,
        toDate(parseDateTime64BestEffort(JSONExtractString(raw_json, 'activity', 'time'))) AS activity_date,
        JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'products')) AS products,
        JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'activityControls')) AS activity_controls,

        -- Location details (if available)
        JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'name') AS location_name,
        JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url') AS location_url,
        JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'sourceUrl') AS location_source_url,

        -- Export metadata
        parseDateTime64BestEffort(JSONExtractString(raw_json, '_export_metadata', 'export_timestamp')) AS export_timestamp,
        JSONExtractString(raw_json, '_export_metadata', 'export_job_id') AS export_job_id,
        toDate(JSONExtractString(raw_json, '_export_metadata', 'export_date')) AS export_date,
        JSONExtractString(raw_json, '_export_metadata', 'source') AS source,
        JSONExtractString(raw_json, '_export_metadata', 'resource') AS resource,
        JSONExtractUInt(raw_json, '_export_metadata', 'record_count') AS record_count,

        -- Keep raw JSON for reference
        raw_json
    FROM s3(
        'http://minio:9000/inbound/raw/google/maps/*.jsonl.gz',
        'admin',
        'minio08062013',
        'LineAsString',
        'raw_json String'
    )
    ORDER BY activity_time DESC
)
SELECT *  FROM raw_json
WHERE location