# ClickHouse Analytics Database

High-performance columnar OLAP database with MinIO S3 integration for fast analytics queries.

## Overview

ClickHouse is a column-oriented database management system (DBMS) for online analytical processing of queries (OLAP). It's integrated with MinIO for:
- S3-backed storage for cost-effective data storage
- Direct queries on data in MinIO using S3 table engine
- Tiered storage (hot data local, cold data on S3)
- Backup and restore to S3

## Architecture

- **ClickHouse Server**: Main database server with HTTP and native protocol interfaces
- **S3 Integration**: Direct integration with MinIO for storage and queries
- **Kafka Integration**: Real-time data ingestion from Kafka topics
- **Storage Policies**: Flexible storage policies for different data lifecycles

## Quick Start

### Start ClickHouse

```bash
docker-compose up -d
```

### Stop ClickHouse

```bash
docker-compose down
```

### View Logs

```bash
docker-compose logs -f clickhouse
```

## Access Points

- **HTTP Interface**: http://localhost:8123
- **Native Protocol**: localhost:9200 (internal port 9000, external 9200 to avoid port conflicts)
- **Metrics**: http://localhost:8123/metrics

## Default Credentials

- **User**: admin
- **Password**: clickhouse2024

## Configuration

### Environment Variables

Key variables in `.env`:
- `CLICKHOUSE_USER`: Admin username
- `CLICKHOUSE_PASSWORD`: Admin password
- `CLICKHOUSE_HTTP_PORT`: HTTP API port (default: 8123)
- `CLICKHOUSE_NATIVE_PORT`: Native protocol port (default: 9200)
- `CLICKHOUSE_S3_BUCKET`: MinIO bucket for ClickHouse data
- `MINIO_ROOT_USER`: MinIO admin username
- `MINIO_ROOT_PASSWORD`: MinIO admin password

### Storage Policies

Three storage policies are configured:

1. **default**: Local disk storage only
2. **s3_main**: Store all data on MinIO S3
3. **tiered**: Hot data on local disk, cold data on S3

### Using Storage Policies

```sql
-- Create table with S3 storage
CREATE TABLE my_table (
    date Date,
    data String
) ENGINE = MergeTree()
ORDER BY date
SETTINGS storage_policy = 's3_main';

-- Create table with tiered storage
CREATE TABLE my_tiered_table (
    date Date,
    data String
) ENGINE = MergeTree()
ORDER BY date
SETTINGS storage_policy = 'tiered';
```

## Usage Examples

### Connect with clickhouse-client

```bash
docker exec -it clickhouse clickhouse-client -u admin --password clickhouse2024
```

### Query Data from MinIO S3

```sql
-- Query JSON files directly from MinIO
SELECT *
FROM s3(
    'http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz',
    'admin',
    'minio08062013',
    'JSONEachRow'
)
LIMIT 10;

-- Create external table for repeated queries
CREATE TABLE spotify_raw
ENGINE = S3(
    'http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz',
    'admin',
    'minio08062013',
    'JSONEachRow'
);
```

### Create Analytics Tables

```sql
-- Create a MergeTree table with S3 storage
CREATE TABLE spotify_tracks (
    played_at DateTime,
    track_name String,
    artist_name String,
    duration_ms UInt32,
    date Date DEFAULT toDate(played_at)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, played_at)
SETTINGS storage_policy = 's3_main';

-- Insert data from S3 source
INSERT INTO spotify_tracks
SELECT
    parseDateTimeBestEffort(played_at) as played_at,
    track.name as track_name,
    track.artists[1].name as artist_name,
    track.duration_ms,
    toDate(parseDateTimeBestEffort(played_at)) as date
FROM s3(
    'http://minio:9000/inbound/raw/spotify/api/tracks/*.jsonl.gz',
    'admin',
    'minio08062013',
    'JSONEachRow'
);
```

### Materialized Views

```sql
-- Create aggregated materialized view
CREATE MATERIALIZED VIEW spotify_daily_stats
ENGINE = MergeTree()
ORDER BY date
SETTINGS storage_policy = 's3_main'
AS SELECT
    toDate(played_at) as date,
    count() as total_plays,
    uniq(track_name) as unique_tracks,
    uniq(artist_name) as unique_artists,
    sum(duration_ms) / 1000 / 60 as total_minutes
FROM spotify_tracks
GROUP BY date;
```

## Kafka Integration

ClickHouse can consume data directly from Kafka topics in real-time using the Kafka table engine. The typical pattern involves three components:

1. **Kafka Engine Table** - Acts as a Kafka consumer
2. **Materialized View** - Transforms data from Kafka
3. **Target MergeTree Table** - Stores the data with S3 storage

### Architecture Flow

```
Kafka Topic → Kafka Engine Table → Materialized View → MergeTree Table (S3)
```

### Complete Example: Spotify Tracks from Kafka

```sql
-- Step 1: Create Kafka consumer table
CREATE TABLE spotify_kafka_queue
(
    played_at String,
    track Tuple(
        id String,
        name String,
        duration_ms UInt32,
        artists Array(Tuple(name String, id String)),
        album Tuple(name String, id String)
    ),
    context Tuple(type String, uri String)
)
ENGINE = Kafka('kafka:9092', 'spotify.tracks.raw', 'clickhouse_consumer', 'JSONEachRow')
SETTINGS
    kafka_num_consumers = 2,
    kafka_thread_per_consumer = 1,
    kafka_skip_broken_messages = 10;

-- Step 2: Create target table with S3 storage
CREATE TABLE spotify_tracks_kafka
(
    played_at DateTime,
    track_id String,
    track_name String,
    artist_name String,
    duration_ms UInt32,
    date Date MATERIALIZED toDate(played_at)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, played_at)
SETTINGS storage_policy = 's3_main';

-- Step 3: Create materialized view to transform and move data
CREATE MATERIALIZED VIEW spotify_kafka_mv TO spotify_tracks_kafka AS
SELECT
    parseDateTimeBestEffort(played_at) as played_at,
    track.id as track_id,
    track.name as track_name,
    track.artists[1].name as artist_name,
    track.duration_ms as duration_ms
FROM spotify_kafka_queue;
```

### Monitor Kafka Consumption

```sql
-- Check Kafka consumer status
SELECT
    database,
    table,
    consumer_id,
    assignments,
    exceptions
FROM system.kafka_consumers;

-- View recent ingested data
SELECT
    played_at,
    track_name,
    artist_name
FROM spotify_tracks_kafka
ORDER BY played_at DESC
LIMIT 10;

-- Check for Kafka-related errors
SELECT
    event_time,
    level,
    message
FROM system.text_log
WHERE logger_name LIKE '%Kafka%'
  AND level >= 'Warning'
ORDER BY event_time DESC
LIMIT 20;
```

### Restart Kafka Consumer

```sql
-- If consumer gets stuck, detach and reattach
DETACH TABLE spotify_kafka_queue;
ATTACH TABLE spotify_kafka_queue;
```

### Performance Tuning

For high-throughput topics:
- Increase `kafka_num_consumers` (e.g., 4-8)
- Increase `kafka_max_block_size` (e.g., 131072)
- Adjust `kafka_poll_timeout_ms` (e.g., 500)
- Use `tiered` storage policy for large datasets

See `examples/kafka-ingestion.sql` for more detailed examples and patterns.

## Backup and Restore

### Create Backup to S3

```sql
-- Backup database to MinIO
BACKUP DATABASE default TO Disk('s3_backup', 'backup_2024_01_01/');
```

### Restore from S3

```sql
-- Restore database from MinIO
RESTORE DATABASE default FROM Disk('s3_backup', 'backup_2024_01_01/');
```

## Monitoring

### Check Storage Usage

```sql
-- View disk usage by table
SELECT
    database,
    table,
    formatReadableSize(sum(bytes)) as size,
    sum(rows) as rows
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY sum(bytes) DESC;

-- View storage policy usage
SELECT
    disk_name,
    formatReadableSize(free_space) as free,
    formatReadableSize(total_space) as total
FROM system.disks;
```

### Query Performance

```sql
-- View recent queries
SELECT
    query_id,
    user,
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes) as read_size,
    query
FROM system.query_log
WHERE type = 'QueryFinish'
ORDER BY event_time DESC
LIMIT 10;
```

## Integration with Data Pipeline

ClickHouse can be used to:
1. Query raw data directly from MinIO S3 buckets
2. Create analytics tables with data from Kafka topics
3. Build materialized views for real-time aggregations
4. Serve as the OLAP layer for dashboard queries

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs clickhouse

# Verify MinIO is running
docker ps | grep minio

# Check network connectivity
docker exec clickhouse ping minio
```

### Can't connect to ClickHouse

```bash
# Test HTTP interface
curl http://localhost:8123/ping

# Test with credentials
curl -u admin:clickhouse2024 http://localhost:8123 -d "SELECT 1"
```

### S3 queries failing

```sql
-- Test S3 connectivity
SELECT * FROM s3(
    'http://minio:9000/clickhouse/test.csv',
    'admin',
    'minio08062013',
    'CSV'
) LIMIT 1;
```

## Resources

- [ClickHouse Documentation](https://clickhouse.com/docs)
- [S3 Table Engine](https://clickhouse.com/docs/en/engines/table-engines/integrations/s3)
- [Storage Configuration](https://clickhouse.com/docs/en/operations/storing-data)
