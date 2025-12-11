{{
    config(
        materialized='view',
        schema='bronze'
    )
}}

/*
    Bronze Layer: YouTube Video Metadata

    Enriched YouTube video metadata from YouTube Data API v3.
    Reads JSONL.gz files from inbound/enriched/youtube/video_metadata/

    Data structure:
    - video_id: YouTube video ID
    - channel_id: Channel ID that published the video
    - channel_title: Channel name
    - duration_seconds: Video duration in seconds
    - category_id: YouTube category ID (numeric string)
    - category_name: Human-readable category name
    - published_at: Video publication timestamp
    - title: Video title
    - description: Video description
    - view_count: Total view count
    - like_count: Total like count
    - comment_count: Total comment count
    - enriched_at: Timestamp when metadata was fetched from YouTube API
*/

SELECT
    -- Video identification
    JSONExtractString(raw_json, 'video_id') AS video_id,

    -- Channel information
    JSONExtractString(raw_json, 'channel_id') AS channel_id,
    JSONExtractString(raw_json, 'channel_title') AS channel_title,

    -- Video metadata
    JSONExtractString(raw_json, 'title') AS title,
    JSONExtractString(raw_json, 'description') AS description,

    -- Duration
    JSONExtractInt(raw_json, 'duration_seconds') AS duration_seconds,

    -- Category
    JSONExtractString(raw_json, 'category_id') AS category_id,
    JSONExtractString(raw_json, 'category_name') AS category_name,

    -- Statistics
    JSONExtractUInt(raw_json, 'view_count') AS view_count,
    JSONExtractUInt(raw_json, 'like_count') AS like_count,
    JSONExtractUInt(raw_json, 'comment_count') AS comment_count,

    -- Timestamps
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'published_at')) AS published_at,
    toDate(parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'published_at'))) AS published_date,
    parseDateTime64BestEffortOrNull(JSONExtractString(raw_json, 'enriched_at')) AS enriched_at,

    -- Keep raw JSON for reference
    raw_json

FROM s3(
    'http://minio:9000/inbound/raw/google/youtube_enriched/video_metadata/*.jsonl.gz',
    'admin',
    'minio08062013',
    'LineAsString',
    'raw_json String'
)
WHERE video_id != ''  -- Only keep records with valid video IDs
ORDER BY enriched_at DESC
