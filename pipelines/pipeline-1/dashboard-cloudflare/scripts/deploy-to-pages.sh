#!/bin/bash

# Deploy to Cloudflare Pages Script
# Simple build and deploy - no configuration needed

set -e  # Exit on error

echo "🚀 Deploying to Cloudflare Pages"
echo "=================================="
echo ""

# Step 1: Build
echo "🔨 Step 1/2: Building project..."
npm run build

# Step 2: Deploy to Pages
echo ""
echo "📤 Step 2/2: Deploying to Cloudflare Pages..."
npx wrangler pages deploy dist

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "💡 Note: If this is your first deployment, set environment variables in the Cloudflare Dashboard:"
echo "   1. Go to: https://dash.cloudflare.com"
echo "   2. Navigate to: Pages > Your Project > Settings > Environment variables"
echo "   3. Add the following variables:"
echo "      - CLICKHOUSE_HOST"
echo "      - CLICKHOUSE_USER"
echo "      - CLICKHOUSE_PASSWORD"
echo "      - CLICKHOUSE_DATABASE"
echo ""
