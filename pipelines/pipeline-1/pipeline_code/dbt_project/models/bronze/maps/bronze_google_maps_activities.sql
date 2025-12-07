{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    Bronze Layer: Google Maps Activities

    Raw Google Maps activity data loaded from MinIO S3 bucket.
    Extracts and parses JSONL.gz files from inbound/raw/google/maps/

    Data includes:
    - Activity headers and titles
    - Timestamps
    - Location information (name, URL, coordinates)
    - Products used
    - Export metadata

    Coordinate Extraction Strategy:
    1. Try latLng field (rare, when exact place is known)
    2. Parse from URL 'center' parameter (common, approximate area)
    3. Returns NULL if neither is available

    Future Enrichment Options:
    - Reverse geocoding: Use coordinates to get detailed address (Google Maps Geocoding API)
    - Place details: Search location name to get place_id, then fetch full details (Google Places API)
    - Travel analysis: Calculate distances between consecutive activities
    - Note: Additional API calls would be done in silver layer or via separate enrichment DAG
*/

SELECT
    -- Activity details
    JSONExtractString(raw_json, 'activity', 'header') AS header,
    JSONExtractString(raw_json, 'activity', 'title') AS title,
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'activity', 'time')) AS activity_time,
    toDate(parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'activity', 'time'))) AS activity_date,
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'products')) AS products,
    JSONExtractArrayRaw(JSONExtractString(raw_json, 'activity', 'activityControls')) AS activity_controls,

    -- Location details (if available)
    JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'name') AS location_name,
    JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url') AS location_url,
    JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'sourceUrl') AS location_source_url,
    JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'address') AS location_address,
    JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'source') AS location_source,

    -- Coordinates extraction (multiple strategies)
    -- Strategy 1: Try latLng field (rare)
    JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'latitude') AS latitude_from_field,
    JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'longitude') AS longitude_from_field,

    -- Strategy 2: Parse from URL center parameter (common: center=47.379011,8.507649)
    toFloat64OrNull(splitByChar(',', extractURLParameter(JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url'), 'center'))[1]) AS latitude_from_url,
    toFloat64OrNull(splitByChar(',', extractURLParameter(JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url'), 'center'))[2]) AS longitude_from_url,

    -- Final coordinates: prefer latLng field, fallback to URL (JSONExtractFloat returns 0 if field doesn't exist)
    if(
        JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'latitude') != 0,
        JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'latitude'),
        toFloat64OrNull(splitByChar(',', extractURLParameter(JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url'), 'center'))[1])
    ) AS latitude,
    if(
        JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'longitude') != 0,
        JSONExtractFloat(raw_json, 'activity', 'locationInfos', 1, 'latLng', 'longitude'),
        toFloat64OrNull(splitByChar(',', extractURLParameter(JSONExtractString(raw_json, 'activity', 'locationInfos', 1, 'url'), 'center'))[2])
    ) AS longitude,

    -- Export metadata
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, '_export_metadata', 'export_timestamp')) AS export_timestamp,
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
-- Keep all activities, even those without specific location names
-- Filter in silver layer if needed for specific analyses
WHERE activity_time IS NOT NULL  -- Only filter out records with missing timestamps
ORDER BY activity_time DESC
