# Spotify DAGs - Setup Guide

This directory contains the Spotify data ingestion pipeline DAGs and supporting code.

## DAGs Overview

1. **spotify_raw_ingestion_jsonl** - Extracts recently played tracks from Spotify API every 15 minutes
2. **spotify_artist_ingestion** - Fetches artist details from discovered artist IDs every 6 hours
3. **spotify_artist_backfill** - One-time backfill to populate all artist details from existing tracks
4. **spotify_dbt_transformation** - Runs dbt transformations to create analytics tables every 30 minutes

## Prerequisites

Before running the Spotify DAGs, you need to:

1. Have a Spotify Developer account
2. Create a Spotify App to get Client ID and Client Secret
3. Configure authentication (see below)

## Spotify Authentication Setup

The Spotify DAGs require OAuth authentication. Follow these steps:

### Step 1: Generate Spotify Token

Run the authentication script **on your local machine** (not in Docker):

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/pipeline_code
python scripts/authenticate_spotify_for_airflow.py
```

This will:
- Open your browser for Spotify login
- Generate a token JSON
- Display the token you need to add to Airflow

### Step 2: Add Token to Airflow

**Option A: Using Airflow UI (Recommended)**

1. Go to http://localhost:8080
2. Login with admin credentials (see `infrastructure/airflow/README.md` for password)
3. Navigate to **Admin > Variables**
4. Click the **'+'** button
5. Set:
   - **Key**: `SPOTIFY_TOKEN_CACHE`
   - **Value**: Paste the JSON from Step 1
6. Click **Save**

**Option B: Using Airflow CLI**

Run the command shown by the authentication script:

```bash
docker exec airflow-standalone airflow variables set SPOTIFY_TOKEN_CACHE '<paste-token-json-here>'
```

### Step 3: Verify Setup

1. Go to Airflow UI: http://localhost:8080
2. Navigate to the `spotify_raw_ingestion_jsonl` DAG
3. Trigger it manually using the play button
4. Check the logs to ensure authentication succeeds

## Token Refresh

- Spotify access tokens expire after **1 hour**
- The refresh token is valid for much longer
- Spotipy automatically refreshes the access token when needed
- The updated token is saved back to Airflow Variables
- **No manual intervention required** after initial setup

## Environment Variables

Make sure these are set in your `.env` file:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

## Troubleshooting

### Issue: "KeyError: 'execution_date'"
**Solution**: This has been fixed. All DAGs now use `logical_date` for Airflow 3.x compatibility.

### Issue: "Browser authentication required"
**Solution**: You need to set up the `SPOTIFY_TOKEN_CACHE` variable in Airflow (see Step 2 above).

### Issue: "Token expired" or "Invalid token"
**Solution**: The token should auto-refresh. If it doesn't:
1. Delete the `SPOTIFY_TOKEN_CACHE` variable from Airflow
2. Run the authentication script again
3. Add the new token to Airflow

### Issue: "Variable.get() got an unexpected keyword argument 'default_var'"
**Solution**: This has been fixed. In Airflow 3.x, the parameter changed from `default_var` to `default`.

### Issue: Deprecated Variable warning
**Solution**: This has been fixed. The code now uses `airflow.sdk.Variable` instead of `airflow.models.Variable`.

## Code Structure

```
spotify/
├── README.md                       # This file
├── __init__.py
├── spotify_api.py                  # Spotify API client functions
└── airflow_cache_handler.py       # Custom cache handler for Airflow Variables

../scripts/
└── authenticate_spotify_for_airflow.py  # Authentication script

../ (DAGs)
├── spotify_ingestion_dag.py        # Main track ingestion DAG
├── spotify_artist_ingestion_dag.py # Artist details ingestion DAG
├── spotify_artist_backfill_dag.py  # One-time artist backfill DAG
└── spotify_dbt_transformation_dag.py # dbt transformation DAG
```

## Data Flow

1. **Track Ingestion** (Every 15 min)
   - Extract recently played tracks from Spotify API
   - Save to S3 as daily JSONL files
   - Publish to Kafka topic `spotify.tracks.raw`
   - Extract artist IDs and publish to `spotify.artist_ids`

2. **Artist Ingestion** (Every 6 hours)
   - Consume artist IDs from Kafka
   - Fetch artist details from Spotify API
   - Save to S3 and publish to Kafka

3. **dbt Transformation** (Every 30 min)
   - Load raw data from S3/Kafka into ClickHouse bronze layer
   - Transform into silver layer (cleaned/enriched)
   - Create gold layer analytics tables

## Airflow 3.x Migration Notes

The following changes were made for Airflow 3.x compatibility:

1. **Imports**: Changed from `airflow.operators.python` to `airflow.providers.standard.operators.python`
2. **Context Variables**: Replaced `execution_date` with `logical_date`
3. **Variables API**:
   - Updated to use `airflow.sdk.Variable` instead of `airflow.models.Variable`
   - Changed `Variable.get(key, default_var=None)` to `Variable.get(key, default=None)`
4. **Authentication**: Using FAB provider for Airflow 3.x

## Support

For issues or questions, check:
- Airflow logs: `infrastructure/airflow/logs/`
- DAG run details in Airflow UI
- Spotify API status: https://status.developer.spotify.com/
