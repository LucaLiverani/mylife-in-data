#!/bin/bash

# Complete Development Environment
# Runs both Vite (frontend) and Wrangler (Functions) servers together

set -e # Exit on error

DEV_SECRETS_FILE=".env.development"

# Cleanup function to kill background processes
cleanup() {
  echo ""
  echo "🛑 Shutting down servers..."
  if [ ! -z "$WRANGLER_PID" ]; then
    kill $WRANGLER_PID 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting Complete Development Environment"
echo "============================================"
echo ""

# Step 1: Check for development secrets
echo "🔒 Step 1/3: Checking for development environment variables..."

if [ ! -f "$DEV_SECRETS_FILE" ]; then
    echo "⚠️  Warning: $DEV_SECRETS_FILE file not found."
    echo "   Creating a template file. Please update it with your development credentials."

    # Create a template .env.development file
    cat > "$DEV_SECRETS_FILE" << 'EOF'
# Development Environment Variables
# Update these values for your local development environment

# ClickHouse connection
CLICKHOUSE_HOST=http://localhost:8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=gold

# Kafka connection (optional - for polling endpoint)
KAFKA_TOPIC=spotify.player.current
EOF

    echo "✅ Template created: $DEV_SECRETS_FILE"
    echo "   Please update this file with your development credentials and run this script again."
    exit 0
else
    echo "✅ Found $DEV_SECRETS_FILE"
fi
echo ""

# Step 2: Build the project (needed for Functions)
echo "🔨 Step 2/3: Building project..."
npm run build
echo "✅ Build complete"
echo ""

# Step 3: Start both servers
echo "🚀 Step 3/3: Starting both servers..."
echo ""

# Export environment variables from .env.development
set -a
source "$DEV_SECRETS_FILE"
set +a

# Start Wrangler Pages dev in the background on port 8788
echo "📡 Starting Cloudflare Functions server on port 8788..."
npx wrangler pages dev dist --port=8788 --compatibility-date=2024-11-16 \
  --binding CLICKHOUSE_HOST="$CLICKHOUSE_HOST" \
  --binding CLICKHOUSE_USER="$CLICKHOUSE_USER" \
  --binding CLICKHOUSE_PASSWORD="$CLICKHOUSE_PASSWORD" \
  --binding CLICKHOUSE_DATABASE="$CLICKHOUSE_DATABASE" \
  --binding KAFKA_TOPIC="$KAFKA_TOPIC" \
  > /tmp/wrangler-dev.log 2>&1 &

WRANGLER_PID=$!

# Wait a bit for wrangler to start
echo "⏳ Waiting for Functions server to start..."
sleep 3

# Check if wrangler is still running
if ! kill -0 $WRANGLER_PID 2>/dev/null; then
  echo "❌ Failed to start Wrangler. Check /tmp/wrangler-dev.log for errors."
  exit 1
fi

echo "✅ Functions server running (PID: $WRANGLER_PID)"
echo ""
echo "📍 Starting Vite dev server on port 3000..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  🌐 Frontend:  http://localhost:3000"
echo "  📡 Functions: http://localhost:8788/api/*"
echo ""
echo "  Press Ctrl+C to stop both servers"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start Vite in foreground
npm run dev

# If vite exits, cleanup
cleanup