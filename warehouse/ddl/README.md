# ClickHouse S3Queue Setup

Automatically processes new JSONL files from MinIO/S3 into ClickHouse.

## Quick Start

### 1. Start Services

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/infrastructure/clickhouse

# Restart with Keeper enabled
docker compose down
docker compose up -d

# Wait for startup
sleep 15
```

### 2. Verify Keeper Connection

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT * FROM system.zookeeper WHERE path='/'"
```

If this returns results, you're good to go!

### 3. Run the SQL Setup

```bash
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < bronze_spotify_tracks_s3_incremental.sql
```

### 4. Verify Tables Created

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM bronze"
```

Expected output:
```
mv_s3queue_spotify_tracks
raw_spotify_tracks
s3queue_spotify_tracks
```

## How It Works

1. S3Queue watches `s3://inbound/raw/spotify/tracks/**/*.jsonl` using named collection `minio_inbound`
2. New files are automatically detected and processed
3. JSON is transformed and loaded into `bronze.raw_spotify_tracks`
4. ClickHouse Keeper prevents duplicate processing

**Note:** S3 credentials are stored in `config/s3_credentials.xml` (separate from code)

## Monitor Processing

### Check processed records

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT count(*) FROM bronze.raw_spotify_tracks"
```

### View recent data

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT track_name, artist_name, played_at
           FROM bronze.raw_spotify_tracks
           ORDER BY ingested_at DESC LIMIT 10"
```

### Check S3Queue status

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT * FROM system.s3queue_log ORDER BY event_time DESC LIMIT 10"
```

## Reset Queue (Reprocess All Files)

```bash
# Drop tables
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "DROP VIEW IF EXISTS bronze.mv_s3queue_spotify_tracks;
           DROP TABLE IF EXISTS bronze.s3queue_spotify_tracks"

# Re-run setup (Step 3 above)
```

## Managing Credentials

S3 credentials are stored in `../../infrastructure/clickhouse/config/s3_credentials.xml`:

```xml
<named_collections>
    <minio_inbound>
        <url>http://minio:9000/inbound/</url>
        <access_key_id>admin</access_key_id>
        <secret_access_key>admin</secret_access_key>
    </minio_inbound>
</named_collections>
```

To change credentials:
1. Edit `s3_credentials.xml`
2. Restart ClickHouse: `docker restart clickhouse`

## Troubleshooting

**No files processing?**
- Check files exist: Upload to MinIO at `inbound/raw/spotify/tracks/*.jsonl`
- Check logs: `docker logs clickhouse --tail 50`

**Keeper connection error?**
- Verify Keeper is running: `docker ps | grep keeper`
- Check config mounted: `docker exec clickhouse ls /etc/clickhouse-server/config.d/zookeeper.xml`

**Credentials error?**
- Verify named collection loaded:
  ```bash
  docker exec clickhouse clickhouse-client --user admin --password admin \
    --query "SELECT * FROM system.named_collections"
  ```

**Need help?**
- Check ClickHouse logs: `docker logs clickhouse`
- Check Keeper logs: `docker logs clickhouse-keeper`

## Artist Data Setup

The artist ingestion pipeline requires two additional tables:

### 1. Raw Artists Table (Bronze Layer)

Stores raw artist data from S3Queue:

```bash
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < bronze_spotify_artists_s3_incremental.sql
```

This creates:
- `bronze.raw_spotify_artists` - Raw artist data with full JSON
- `bronze.s3queue_spotify_artists` - S3Queue table watching `inbound/raw/spotify/api/artists/*.jsonl`
- `bronze.mv_s3queue_spotify_artists` - Materialized view for auto-processing

### 2. Artists Dimension Table

Tracks current state of each artist with deduplication:

```bash
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < spotify_artists_dimension.sql
```

This creates:
- `spotify.spotify_artists` - Dimension table with latest artist state
- `spotify.mv_spotify_artists_dimension` - Auto-populates from raw data

### Verify Artist Tables

```bash
# Check bronze tables
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM bronze"

# Check spotify database
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM spotify"
```

### Monitor Artist Ingestion

```bash
# Count artists
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT count(*) as total_artists,
           count(DISTINCT artist_id) as unique_artists
           FROM bronze.raw_spotify_artists"

# View recent artists
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT artist_name, followers_total, popularity, genres
           FROM bronze.raw_spotify_artists
           ORDER BY ingested_at DESC LIMIT 10"

# Check artists needing refresh (older than 7 days)
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT artist_id, artist_name, last_updated
           FROM spotify.spotify_artists
           WHERE last_updated < now() - toIntervalDay(7)
           LIMIT 10"
```