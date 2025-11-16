DROP VIEW IF EXISTS bronze.mv_spotify_current_track;
DROP VIEW IF EXISTS bronze.mv_kafka_to_null;
DROP TABLE IF EXISTS bronze.null_spotify_buffer;
DROP TABLE IF EXISTS bronze.raw_spotify_current_track_kafka;
DROP TABLE IF EXISTS bronze.queue_spotify_tracks;

CREATE TABLE IF NOT EXISTS bronze.queue_spotify_tracks (
    message String  -- Raw JSON message as string
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'spotify.player.current',
    kafka_group_name = 'clickhouse_spotify_current_track',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

-- 2. Create the target table (persistent storage)
CREATE TABLE IF NOT EXISTS bronze.raw_spotify_current_track_kafka (
    -- Track info
    track_id String,
    track_name String,
    track_uri String,
    track_duration_ms UInt32,

    -- Album info
    album_id String,
    album_name String,
    album_uri String,
    album_images Array(String),

    -- Artist info (first artist)
    artist_id String,
    artist_name String,
    artist_uri String,

    -- All artists as array (for multi-artist tracks)
    artists_ids Array(String),
    artists_names Array(String),

    -- Context (playlist/album where it was played)
    context_type String,
    context_uri String,

    -- Playback info
    progress_ms UInt32,
    is_playing Bool,
    captured_at DateTime64(3),

    -- Device info
    device_id String,
    device_name String,
    device_type String,
    device_volume_percent UInt8,

    -- Store complete raw JSON for reference
    raw_json String

) ENGINE = ReplacingMergeTree(captured_at)
PARTITION BY toYYYYMM(captured_at)
ORDER BY (track_id, captured_at)
SETTINGS index_granularity = 8192;



-- 3. Create Null table to force Kafka consumption (workaround for CH 25.x startup dependency bug)
CREATE TABLE IF NOT EXISTS bronze.null_spotify_buffer (
    message String
) ENGINE = Null;

-- 4. Create first MV: Kafka → Null (this starts the Kafka consumer immediately)
CREATE MATERIALIZED VIEW bronze.mv_kafka_to_null TO bronze.null_spotify_buffer AS
SELECT message FROM bronze.queue_spotify_tracks;

-- 5. Create materialized view to process messages: Null → Final table
CREATE MATERIALIZED VIEW bronze.mv_spotify_current_track TO bronze.raw_spotify_current_track_kafka AS
SELECT
    JSONExtractString(message, 'track_id') AS track_id,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'track_name'), '') AS track_name,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'track_uri'), '') AS track_uri,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractUInt(message, 'duration_ms'), 0) AS track_duration_ms,

    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'album', 'id'), '') AS album_id,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'album', 'name'), '') AS album_name,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'album', 'uri'), '') AS album_uri,
    if(JSONExtractBool(message, 'is_playing'), arrayMap(x -> JSONExtractString(x, 'url'), JSONExtractArrayRaw(JSONExtractString(message, 'album', 'images'))), []) AS album_images,

    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'artists', 1, 'id'), '') AS artist_id,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'artists', 1, 'name'), '') AS artist_name,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'artists', 1, 'uri'), '') AS artist_uri,

    if(JSONExtractBool(message, 'is_playing'), arrayMap(x -> JSONExtractString(x, 'id'), JSONExtractArrayRaw(JSONExtractString(message, 'artists'))), []) AS artists_ids,
    if(JSONExtractBool(message, 'is_playing'), arrayMap(x -> JSONExtractString(x, 'name'), JSONExtractArrayRaw(JSONExtractString(message, 'artists'))), []) AS artists_names,

    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'context', 'type'), '') AS context_type,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'context', 'uri'), '') AS context_uri,

    if(JSONExtractBool(message, 'is_playing'), JSONExtractUInt(message, 'progress_ms'), 0) AS progress_ms,
    JSONExtractBool(message, 'is_playing') AS is_playing,
    parseDateTime64BestEffort(JSONExtractString(message, 'timestamp')) AS captured_at,

    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'device', 'id'), '') AS device_id,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'device', 'name'), '') AS device_name,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractString(message, 'device', 'type'), '') AS device_type,
    if(JSONExtractBool(message, 'is_playing'), JSONExtractUInt(message, 'device', 'volume_percent'), 0) AS device_volume_percent,

    message AS raw_json

FROM bronze.queue_spotify_tracks
WHERE (JSONExtractString(message, 'track_id') != '' AND JSONExtractBool(message, 'is_playing') = true) OR JSONExtractBool(message, 'is_playing') = false;