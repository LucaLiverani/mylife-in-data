# Spotify Analytics Pipeline - Deployment Guide

Complete end-to-end deployment guide for the improved analytics pipeline.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Data Ingestion                          │
├─────────────────────────────────────────────────────────────────┤
│  Airflow DAG (every 15 min)                                     │
│  ├─ Extract Spotify API → S3 (tracks.jsonl.gz)                 │
│  └─ Extract Artist IDs → Kafka                                  │
│                                                                  │
│  Airflow DAG (every 6 hours)                                    │
│  ├─ Collect Artist IDs (Kafka + ClickHouse)                    │
│  ├─ Fetch Artist Details (batch 50)                            │
│  └─ Save to S3 (artists.jsonl)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ClickHouse Bronze Layer                     │
├─────────────────────────────────────────────────────────────────┤
│  S3Queue Auto-Ingest                                            │
│  ├─ bronze.raw_spotify_tracks                                   │
│  └─ bronze.raw_spotify_artists                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    dbt Transformations (every 30 min)           │
├─────────────────────────────────────────────────────────────────┤
│  Silver Layer (Views)                                           │
│  ├─ silver_spotify_tracks (cleaned, deduplicated)              │
│  └─ silver_spotify_artists (latest details)                    │
│                                                                  │
│  Gold Layer (Tables - Dashboard Ready)                          │
│  ├─ gold_spotify_kpis                                          │
│  ├─ gold_spotify_top_artists                                   │
│  ├─ gold_spotify_genres                                        │
│  ├─ gold_spotify_daily_listening                               │
│  └─ gold_spotify_recent_tracks                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Next.js Dashboard                           │
├─────────────────────────────────────────────────────────────────┤
│  API Routes (query ClickHouse gold tables)                      │
│  ├─ /api/spotify/data → KPIs, Artists, Genres, Time Series    │
│  ├─ /api/spotify/summary → Quick stats                         │
│  └─ /api/spotify/recent → Recent tracks                        │
└─────────────────────────────────────────────────────────────────┘
```

## Step 1: ClickHouse Setup

### 1.1 Create Bronze Tables

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/pipeline_code/clickhouse

# Create tracks bronze table
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < bronze_spotify_tracks_s3_incremental.sql

# Create artists bronze table
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < bronze_spotify_artists_s3_incremental.sql

# Create artists dimension table
docker exec -i clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --multiquery < spotify_artists_dimension.sql
```

### 1.2 Verify Tables Created

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM bronze"

docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM spotify"
```

Expected output:
- bronze: `raw_spotify_tracks`, `raw_spotify_artists`, `s3queue_*`, `mv_*`
- spotify: `spotify_artists`, `mv_spotify_artists_dimension`

## Step 2: Airflow Setup

### 2.1 Rebuild Airflow with dbt

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/infrastructure/airflow

# Rebuild with updated requirements.txt (includes dbt-clickhouse)
docker-compose build

# Restart Airflow
docker-compose down
docker-compose up -d
```

### 2.2 Verify DAGs Loaded

Visit `http://localhost:8080` and check for:
- `spotify_raw_ingestion_jsonl` (every 15 min)
- `spotify_artist_ingestion` (every 6 hours)
- `spotify_dbt_transformation` (every 30 min)

## Step 3: Initialize dbt

### 3.1 Create Analytics Database

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "CREATE DATABASE IF NOT EXISTS analytics"
```

### 3.2 Test dbt Connection

```bash
# Enter Airflow scheduler container
docker exec -it <airflow-scheduler-container> bash

# Test dbt
cd /opt/airflow/dags/dbt_project
dbt debug --profiles-dir .
```

### 3.3 Run dbt First Time

```bash
# Still inside Airflow container
dbt run --profiles-dir .
```

This creates:
- `analytics.silver_spotify_tracks` (view)
- `analytics.silver_spotify_artists` (view)
- `analytics.gold_spotify_kpis` (table)
- `analytics.gold_spotify_top_artists` (table)
- `analytics.gold_spotify_genres` (table)
- `analytics.gold_spotify_daily_listening` (table)
- `analytics.gold_spotify_recent_tracks` (table)

### 3.4 Verify Gold Tables

```bash
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SHOW TABLES FROM analytics"

# Check row counts
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT COUNT(*) FROM analytics.gold_spotify_kpis"
```

## Step 4: Next.js Dashboard Setup

### 4.1 Install Dependencies

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/dashboard-nextjs

# Install ClickHouse client
npm install
```

### 4.2 Configure Environment

Ensure `.env.local` has:
```bash
CLICKHOUSE_HOST=http://localhost:8123
CLICKHOUSE_USER=admin
CLICKHOUSE_PASSWORD=clickhouse08062013
CLICKHOUSE_DATABASE=analytics

KAFKA_BOOTSTRAP_SERVERS=localhost:9093
KAFKA_TOPIC=spotify.player.current
```

### 4.3 Start Dashboard

```bash
npm run dev
```

Visit: `http://localhost:3000/spotify`

## Step 5: Enable Airflow DAGs

### 5.1 Trigger Manual Runs (First Time)

1. **Track Ingestion**: Run `spotify_raw_ingestion_jsonl` manually
   - Fetches your recent Spotify history
   - Publishes to S3 and Kafka

2. **Artist Ingestion**: Run `spotify_artist_ingestion` manually
   - Fetches artist details for all discovered artists
   - Publishes to S3

3. **dbt Transformation**: Run `spotify_dbt_transformation` manually
   - Creates gold tables from bronze data
   - Should complete in <1 minute

### 5.2 Check Data Flow

```bash
# Check bronze layer
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT COUNT(*) as tracks FROM bronze.raw_spotify_tracks"

docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT COUNT(*) as artists FROM bronze.raw_spotify_artists"

# Check gold layer
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT * FROM analytics.gold_spotify_kpis"
```

### 5.3 Enable Automatic Scheduling

Turn on all DAGs in Airflow UI:
- `spotify_raw_ingestion_jsonl` → Auto-runs every 15 min
- `spotify_artist_ingestion` → Auto-runs every 6 hours
- `spotify_dbt_transformation` → Auto-runs every 30 min

## Monitoring

### Check Pipeline Health

```bash
# Track ingestion rate
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT
    toDate(played_at) as date,
    COUNT(*) as tracks
  FROM bronze.raw_spotify_tracks
  GROUP BY date
  ORDER BY date DESC
  LIMIT 7"

# Check dbt refresh times
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT updated_at FROM analytics.gold_spotify_kpis"
```

### Airflow Logs

- Track DAG: Check for API errors or S3 upload failures
- Artist DAG: Check for ClickHouse query errors
- dbt DAG: Check for SQL compilation or execution errors

## Troubleshooting

### No Data in Dashboard

1. **Check bronze tables have data**:
   ```bash
   SELECT COUNT(*) FROM bronze.raw_spotify_tracks
   ```

2. **Run dbt manually**:
   ```bash
   docker exec -it airflow-scheduler bash
   cd /opt/airflow/dags/dbt_project
   dbt run --profiles-dir .
   ```

3. **Check gold tables**:
   ```bash
   SELECT * FROM analytics.gold_spotify_kpis
   ```

### dbt Errors

```bash
# Compile without running (check SQL)
dbt compile --profiles-dir .

# View compiled SQL
cat target/compiled/spotify_analytics/models/gold/gold_spotify_kpis.sql
```

### Artist Ingestion Not Working

1. Check Kafka topic has artist IDs:
   ```bash
   docker exec -it kafka kafka-console-consumer \
     --bootstrap-server localhost:9092 \
     --topic spotify.artist_ids \
     --from-beginning
   ```

2. Check ClickHouse dimension table:
   ```bash
   SELECT artist_id, last_updated
   FROM spotify.spotify_artists
   ORDER BY last_updated DESC
   LIMIT 10
   ```

## Performance Optimization

### Recommended Settings

```sql
-- Optimize gold tables for faster queries
OPTIMIZE TABLE analytics.gold_spotify_kpis FINAL;
OPTIMIZE TABLE analytics.gold_spotify_top_artists FINAL;
OPTIMIZE TABLE analytics.gold_spotify_genres FINAL;
OPTIMIZE TABLE analytics.gold_spotify_daily_listening FINAL;
```

### Monitoring Query Performance

```bash
# Check query execution times
docker exec clickhouse clickhouse-client \
  --user admin --password clickhouse08062013 \
  --query "SELECT
    query,
    query_duration_ms
  FROM system.query_log
  WHERE type = 'QueryFinish'
  ORDER BY event_time DESC
  LIMIT 10"
```

## Next Steps

1. **Add More Gold Tables**: Create additional aggregations for new dashboard features
2. **Optimize dbt**: Add incremental models for large datasets
3. **Add Tests**: Expand dbt test coverage for data quality
4. **Add Alerts**: Set up Airflow alerts for DAG failures
5. **Scale**: Increase Airflow parallelism if processing more data sources

## Architecture Benefits

✅ **No FastAPI** - Simplified tech stack
✅ **Pre-aggregated Data** - Fast dashboard queries (<100ms)
✅ **Automatic Refresh** - dbt keeps gold tables updated
✅ **Type Safety** - dbt models are version controlled
✅ **Testable** - dbt tests ensure data quality
✅ **Scalable** - Add new metrics by adding dbt models
