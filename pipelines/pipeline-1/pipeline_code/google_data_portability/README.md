# Google Data Portability API Integration

This module provides Python tools to export your behavioral data from Google services (YouTube, Maps, Search, etc.) using the Google Data Portability API.

## Setup Instructions

### 1. Create Google Cloud Project & Enable API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "mylife-data-portability")
3. Navigate to **APIs & Services** → **Library**
4. Search for "Data Portability API" and click **Enable**

### 2. Configure OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If first time, configure OAuth consent screen:
   - User Type: **External** (for personal use)
   - Fill in app name, support email
   - Add scopes:
     - `https://www.googleapis.com/auth/dataportability.myactivity.youtube`
     - `https://www.googleapis.com/auth/dataportability.myactivity.maps`
   - Add test users: Your Gmail address
4. Create OAuth Client ID:
   - Application type: **Desktop app**
   - Name: "Data Portability Client"
5. Download credentials JSON file
6. Save as `pipeline_code/client_secrets.json`

⚠️ **IMPORTANT**: Add `client_secrets.json` to `.gitignore` - never commit credentials!

### 3. Install Dependencies

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-1/pipeline_code
pip install google-auth-oauthlib google-api-python-client --upgrade
```

### 4. Authenticate

Run the authentication script to create a cached token:

```bash
python google_data_portability/authenticate.py
```

This will:
- Open a browser for Google OAuth login
- Request permissions for YouTube and Maps data
- Cache the token in `tokens/.google_portability_token.pickle`

## Usage

### Export YouTube Activity Data

Export all YouTube viewing history:

```bash
python google_data_portability/export_youtube_data.py
```

Export YouTube data for a specific date range:

```bash
python google_data_portability/export_youtube_data.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

Options:
- `--start-date YYYY-MM-DD` - Start date for data export
- `--end-date YYYY-MM-DD` - End date for data export
- `--output-dir PATH` - Output directory (default: `data/google_exports/youtube`)
- `--poll-interval SECONDS` - Status check interval (default: 30)

### Export Google Maps Activity Data

Export all Maps location and activity history:

```bash
python google_data_portability/export_maps_data.py
```

Export Maps data for a specific date range:

```bash
python google_data_portability/export_maps_data.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

Options are the same as YouTube export script.

## Available Data Scopes

The API client supports multiple Google service scopes:

### YouTube
- `youtube_activity` - Viewing history (My Activity)
- `youtube_channel` - Channel metadata and settings
- `youtube_comments` - Your comments
- `youtube_subscriptions` - Subscribed channels
- `youtube_playlists` - Your playlists
- `youtube_music` - YouTube Music data

### Maps
- `maps_activity` - Location history (My Activity)
- `maps_starred_places` - Saved/starred locations
- `maps_reviews` - Your reviews
- `maps_commute_routes` - Commute settings
- `maps_photos` - Photos you uploaded

### Other Services
- `search_activity` - Google Search history
- `chrome_history` - Chrome browsing history
- `shopping_activity` - Shopping activity

## How It Works

The Data Portability API uses an asynchronous export model:

1. **Initiate**: Request an export job with `initiate_archive()`
2. **Poll**: Check status with `get_archive_state()` every 30s
3. **Download**: When complete, download files from signed URLs

Export jobs can take anywhere from a few minutes to several hours depending on:
- Amount of data to export
- Google's processing queue
- Selected time range

## Output Format

Exported data is typically provided as:
- **ZIP archives** containing JSON files
- **CSV files** for structured data (e.g., video metadata)
- **Media files** (e.g., uploaded videos) when applicable

Each export includes:
- Activity timestamps
- Interaction data
- Metadata (titles, descriptions, etc.)
- Associated media when relevant

## Important Notes

⚠️ **API Limitations**:
- OAuth tokens in "Testing" mode expire in 7 days
- Exports can only be run once per resource unless you call `reset_authorization()`
- Maximum export duration filter: 180 days (for time-based access)
- Some data may have retention limits (e.g., YouTube watch history ~8 months)

⚠️ **Privacy**:
- Downloads contain sensitive personal data
- Store securely and never commit to version control
- Consider encryption for stored exports

⚠️ **Rate Limits**:
- There may be quotas on how frequently you can export
- Failed jobs don't immediately allow retries

## Next Steps

After exporting data, you can:
1. Parse the JSON/CSV files
2. Load into your data warehouse (ClickHouse)
3. Build dbt models for transformation
4. Create visualizations in your dashboard

See the Spotify integration for a reference architecture.