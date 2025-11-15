-- 1. Create the Kafka queue table (consumes from Kafka)
CREATE TABLE IF NOT EXISTS bronze.queue_spotify_tracks (
    message String  -- Raw JSON message as string
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'spotify.tracks.raw',
    kafka_group_name = 'clickhouse_spotify_tracks',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

-- 2. Create the target table (persistent storage)
CREATE TABLE IF NOT EXISTS bronze.raw_spotify_tracks_kafka (
    -- Track info (extracted from nested JSON)
    track_id String,
    track_name String,
    track_uri String,
    track_popularity UInt16,
    track_duration_ms UInt32,
    track_explicit Bool,
    track_preview_url String,
    isrc String,
    
    -- Album info
    album_id String,
    album_name String,
    album_type String,
    album_release_date Nullable(Date),
    album_uri String,
    
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
    played_at DateTime64(3),
    
    -- Ingestion metadata
    ingested_at DateTime64(6),
    execution_date DateTime,
    dag_id String,
    run_id String,
    source String,
    
    -- Store complete raw JSON for reference
    raw_json String
    
) ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(played_at)
ORDER BY (track_id, played_at)
SETTINGS index_granularity = 8192;



-- 3. Create materialized view to process messages
CREATE MATERIALIZED VIEW bronze.mv_spotify_tracks TO bronze.raw_spotify_tracks_kafka AS
SELECT
    JSONExtractString(message, 'raw_item', 'track', 'id') AS track_id,
    JSONExtractString(message, 'raw_item', 'track', 'name') AS track_name,
    JSONExtractString(message, 'raw_item', 'track', 'uri') AS track_uri,
    JSONExtractUInt(message, 'raw_item', 'track', 'popularity') AS track_popularity,
    JSONExtractUInt(message, 'raw_item', 'track', 'duration_ms') AS track_duration_ms,
    JSONExtractBool(message, 'raw_item', 'track', 'explicit') AS track_explicit,
    JSONExtractString(message, 'raw_item', 'track', 'preview_url') AS track_preview_url,
    JSONExtractString(message, 'raw_item', 'track', 'external_ids', 'isrc') AS isrc,
    
    JSONExtractString(message, 'raw_item', 'track', 'album', 'id') AS album_id,
    JSONExtractString(message, 'raw_item', 'track', 'album', 'name') AS album_name,
    JSONExtractString(message, 'raw_item', 'track', 'album', 'album_type') AS album_type,
    toDate(parseDateTimeBestEffortOrNull(JSONExtractString(message, 'raw_item', 'track', 'album', 'release_date'))) AS album_release_date,
    JSONExtractString(message, 'raw_item', 'track', 'album', 'uri') AS album_uri,
    
    JSONExtractString(message, 'raw_item', 'track', 'artists', 1, 'id') AS artist_id,
    JSONExtractString(message, 'raw_item', 'track', 'artists', 1, 'name') AS artist_name,
    JSONExtractString(message, 'raw_item', 'track', 'artists', 1, 'uri') AS artist_uri,
    
    arrayMap(x -> JSONExtractString(x, 'id'), 
             JSONExtractArrayRaw(JSONExtractString(message, 'raw_item', 'track', 'artists'))) AS artists_ids,
    arrayMap(x -> JSONExtractString(x, 'name'), 
             JSONExtractArrayRaw(JSONExtractString(message, 'raw_item', 'track', 'artists'))) AS artists_names,
    
    JSONExtractString(message, 'raw_item', 'context', 'type') AS context_type,
    JSONExtractString(message, 'raw_item', 'context', 'uri') AS context_uri,
    
    parseDateTime64BestEffort(JSONExtractString(message, 'raw_item', 'played_at')) AS played_at,
    
    parseDateTime64BestEffort(JSONExtractString(message, '_ingestion_metadata', 'ingested_at')) AS ingested_at,
    parseDateTime64BestEffort(JSONExtractString(message, '_ingestion_metadata', 'execution_date')) AS execution_date,
    JSONExtractString(message, '_ingestion_metadata', 'dag_id') AS dag_id,
    JSONExtractString(message, '_ingestion_metadata', 'run_id') AS run_id,
    JSONExtractString(message, '_ingestion_metadata', 'source') AS source,
    
    message AS raw_json

FROM bronze.queue_spotify_tracks;