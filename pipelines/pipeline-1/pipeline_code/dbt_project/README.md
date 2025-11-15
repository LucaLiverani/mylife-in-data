# Spotify Analytics dbt Project

This dbt project transforms raw Spotify listening data into analytics-ready tables for the dashboard.

## Architecture

```
Bronze (Raw) → Silver (Cleaned) → Gold (Aggregated)
```

### Layers

**Bronze Layer** (ClickHouse bronze schema)
- `raw_spotify_tracks` - Raw listening history from S3Queue
- `raw_spotify_artists` - Raw artist details from S3Queue

**Silver Layer** (Views)
- `silver_spotify_tracks` - Deduplicated, cleaned tracks with derived fields
- `silver_spotify_artists` - Latest artist details

**Gold Layer** (Tables - Dashboard Ready)
- `gold_spotify_kpis` - Single row with all KPI metrics
- `gold_spotify_top_artists` - Top 100 artists with enriched details
- `gold_spotify_genres` - Genre distribution
- `gold_spotify_daily_listening` - Daily time series with moving averages
- `gold_spotify_recent_tracks` - Last 100 played tracks

## Setup

### 1. Install dbt Dependencies

The required packages are in `requirements.txt`:
```bash
pip install dbt-core dbt-clickhouse
```

### 2. Test Connection

```bash
cd /opt/airflow/dags/dbt_project
dbt debug --profiles-dir .
```

### 3. Run Transformations

```bash
# Run all models
dbt run --profiles-dir .

# Run specific layer
dbt run --select silver.* --profiles-dir .
dbt run --select gold.* --profiles-dir .

# Run specific model
dbt run --select gold_spotify_kpis --profiles-dir .
```

### 4. Run Tests

```bash
dbt test --profiles-dir .
```

### 5. Generate Documentation

```bash
dbt docs generate --profiles-dir .
dbt docs serve --profiles-dir .
```

## Scheduling

The `spotify_dbt_transformation` DAG runs every 30 minutes:
- Installs dbt dependencies
- Runs all models (silver → gold)
- Runs tests
- Logs completion

## Configuration

Edit `dbt_project.yml` to change:
- `lookback_days`: Number of days to include in analysis (default: 365)
- Materialization strategies
- Schema names

## Queries for Dashboard

The Next.js dashboard queries these gold tables:

```sql
-- KPIs
SELECT * FROM gold_spotify_kpis LIMIT 1;

-- Top Artists
SELECT * FROM gold_spotify_top_artists ORDER BY rank LIMIT 10;

-- Genres
SELECT * FROM gold_spotify_genres ORDER BY rank LIMIT 20;

-- Daily Listening
SELECT * FROM gold_spotify_daily_listening ORDER BY date DESC LIMIT 365;

-- Recent Tracks
SELECT * FROM gold_spotify_recent_tracks ORDER BY recency_rank LIMIT 50;
```

## Development

### Adding New Models

1. Create SQL file in `models/silver/` or `models/gold/`
2. Add model configuration in `schema.yml`
3. Run: `dbt run --select your_model_name`
4. Test: `dbt test --select your_model_name`

### Debugging

```bash
# Compile SQL without running
dbt compile --select model_name

# Check compiled SQL
cat target/compiled/spotify_analytics/models/gold/gold_spotify_kpis.sql
```

## Monitoring

Check Airflow for:
- DAG run status
- dbt logs
- Test failures

Check ClickHouse for:
- Table sizes: `SELECT table, formatReadableSize(total_bytes) FROM system.tables WHERE database = 'analytics'`
- Row counts: `SELECT COUNT(*) FROM analytics.gold_spotify_kpis`
