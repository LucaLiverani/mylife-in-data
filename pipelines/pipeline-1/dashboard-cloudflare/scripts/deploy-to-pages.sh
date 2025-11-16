#!/bin/bash

# Deploy to Cloudflare Pages Script

set -e  # Exit on error

# Load configuration
CONFIG_FILE=".deployment-config"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    echo "Please run: ./scripts/setup-config.sh first"
    exit 1
fi

source "$CONFIG_FILE"

echo "🚀 Deploying to Cloudflare Pages"
echo "=================================="
echo ""
echo "Project: $PROJECT_NAME"
echo ""

# Step 1: Export fallback data
echo "📊 Step 1/4: Exporting fallback data..."
./scripts/export-fallback-data.sh

# Step 2: Build
echo ""
echo "🔨 Step 2/4: Building project..."
npm run build

# Step 3: Deploy to Pages
echo ""
echo "📤 Step 3/4: Deploying to Cloudflare Pages..."
npm run pages:deploy

# Step 4: Set environment variables
echo ""
echo "🔐 Step 4/4: Setting environment variables..."

echo "Setting CLICKHOUSE_HOST..."
echo "$CLICKHOUSE_HOST" | npx wrangler pages secret put CLICKHOUSE_HOST --project-name="$PROJECT_NAME"
sleep 2

echo "Setting CLICKHOUSE_USER..."
echo "$CLICKHOUSE_USER" | npx wrangler pages secret put CLICKHOUSE_USER --project-name="$PROJECT_NAME"
sleep 2

echo "Setting CLICKHOUSE_PASSWORD..."
echo "$CLICKHOUSE_PASSWORD" | npx wrangler pages secret put CLICKHOUSE_PASSWORD --project-name="$PROJECT_NAME"
sleep 2

echo "Setting CLICKHOUSE_DATABASE..."
echo "$CLICKHOUSE_DATABASE" | npx wrangler pages secret put CLICKHOUSE_DATABASE --project-name="$PROJECT_NAME"
sleep 2

# Verify
echo ""
echo "✅ Verifying secrets..."
npx wrangler pages secret list --project-name="$PROJECT_NAME"

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📍 Your site is live at:"
echo "   https://$PROJECT_NAME.pages.dev"
echo ""
echo "🎯 Next steps:"
echo "  1. Set up tunnel: ./scripts/setup-tunnel.sh"
echo "  2. Add custom domain via Cloudflare Dashboard"
