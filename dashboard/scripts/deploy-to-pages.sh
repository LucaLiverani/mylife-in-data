#!/bin/bash

# Deploy to Cloudflare Pages Script
# Builds, uploads secrets, and deploys the project.

set -e # Exit on error

PRODUCTION_SECRETS_FILE=".env.production"

echo "🚀 Deploying to Cloudflare Pages"
echo "=================================="
echo ""

# Step 1: Build
echo "🔨 Step 1/3: Building project..."
npm run build
echo "✅ Build complete."
echo ""

# Step 2: Upload Secrets
echo "🔒 Step 2/3: Uploading secrets from $PRODUCTION_SECRETS_FILE..."

# Check if production secrets file exists
if [ ! -f "$PRODUCTION_SECRETS_FILE" ]; then
    echo "⚠️  Error: $PRODUCTION_SECRETS_FILE file not found. Cannot upload secrets."
    echo "   Please create this file with your production environment variables."
    exit 1 # Exit if production secrets are missing
else
    # Read each line from production secrets file, parse it, and upload the secret
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Ignore comments and empty lines
        if [[ "$line" =~ ^\s*# ]] || [[ -z "$line" ]]; then
            continue
        fi

        # Extract key and value
        KEY=$(echo "$line" | cut -d '=' -f 1)
        VALUE=$(echo "$line" | cut -d '=' -f 2-)

        # Securely upload the secret
        echo "   - Uploading secret: $KEY"
        echo "$VALUE" | npx wrangler pages secret put "$KEY"
    done < "$PRODUCTION_SECRETS_FILE"
    echo "✅ Secrets uploaded successfully."
fi
echo ""

# Step 3: Deploy to Pages
# --branch=main forces every deploy (regardless of the laptop's current git
# branch) to promote to the production environment, so the custom domain
# (mylife-in-data.com) and the uploaded Pages secrets are picked up. Without
# this, a deploy from `dev` lands as a preview at `dev.mylife-in-data.pages.dev`
# with no production secrets.
echo "📤 Step 3/3: Deploying to Cloudflare Pages..."
npx wrangler pages deploy dist --branch=main
echo ""

echo "🎉 Deployment complete!"
echo ""
