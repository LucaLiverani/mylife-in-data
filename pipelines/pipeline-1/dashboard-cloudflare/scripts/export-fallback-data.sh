#!/bin/bash

# Export current data as static JSON for fallback
CLICKHOUSE_HOST=${CLICKHOUSE_HOST:-"http://localhost:8123"}
CLICKHOUSE_USER=${CLICKHOUSE_USER:-"admin"}
CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD:-"clickhouse08062013"}
CLICKHOUSE_DB=${CLICKHOUSE_DATABASE:-"gold"}
OUTPUT_DIR="./public/fallback-data"

echo "🔄 Exporting fallback data from ClickHouse..."
echo "   Host: $CLICKHOUSE_HOST"
echo "   Database: $CLICKHOUSE_DB"
echo ""

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Function to export query to JSON
export_query() {
  local name=$1
  local query=$2
  local output_file="$OUTPUT_DIR/$name.json"

  echo "📊 Exporting $name..."

  curl -s -u "$CLICKHOUSE_USER:$CLICKHOUSE_PASSWORD" "$CLICKHOUSE_HOST" \
    --data-binary "$query" \
    > "$output_file"

  if [ $? -eq 0 ]; then
    echo "   ✅ Saved to $output_file ($(wc -c < "$output_file") bytes)"
  else
    echo "   ❌ Failed to export $name"
  fi
}

# Overview stats
export_query "overview-stats" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_kpis LIMIT 1 FORMAT JSONEachRow"

# Spotify KPIs
export_query "spotify-kpis" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_kpis LIMIT 1 FORMAT JSONEachRow"

# Spotify top artists
export_query "spotify-top-artists" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_top_artists ORDER BY rank LIMIT 10 FORMAT JSONEachRow"

# Spotify genres
export_query "spotify-genres" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_genres ORDER BY rank LIMIT 20 FORMAT JSONEachRow"

# Spotify time series
export_query "spotify-timeseries" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_daily_listening ORDER BY date FORMAT JSONEachRow"

# Spotify recent tracks
export_query "spotify-recent" \
  "SELECT * FROM ${CLICKHOUSE_DB}.gold_spotify_recent_tracks ORDER BY recency_rank LIMIT 50 FORMAT JSONEachRow"

# Daily listening for overview
export_query "daily-listening" \
  "SELECT date, play_count AS spotify, 0 AS youtube, 0 AS google, 0 AS maps FROM ${CLICKHOUSE_DB}.gold_spotify_daily_listening ORDER BY date DESC LIMIT 30 FORMAT JSONEachRow"

echo ""
echo "✅ Fallback data export complete!"
echo ""
echo "📁 Files created:"
ls -lh "$OUTPUT_DIR/"

echo ""
echo "📊 Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
