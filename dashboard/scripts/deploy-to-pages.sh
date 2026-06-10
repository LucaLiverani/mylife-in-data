#!/bin/bash

# Deploy to Cloudflare Pages (manual / emergency path).
#
# The normal path is CI: pushes to main deploy automatically via
# .github/workflows/ci.yml. Use this script for emergency deploys, previews,
# and secret rotation.
#
# Usage:
#   ./scripts/deploy-to-pages.sh             # build + deploy to production
#   ./scripts/deploy-to-pages.sh --preview   # build + deploy to the Pages
#                                            # preview environment (branch
#                                            # alias dev.<project>.pages.dev,
#                                            # no production secrets => every
#                                            # endpoint serves mocks)
#   ./scripts/deploy-to-pages.sh --secrets   # also (re-)upload production
#                                            # Function secrets from
#                                            # .env.production before deploying
#
# wrangler is pinned exactly in package.json (4.94+ silently swallows
# FunctionsBuildError); `npm ci` below makes the lockfile, not whatever is in
# node_modules, decide the version that runs.

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PRODUCTION_SECRETS_FILE=".env.production"
UPLOAD_SECRETS=0
TARGET_BRANCH="main"

for arg in "$@"; do
    case "$arg" in
        --secrets) UPLOAD_SECRETS=1 ;;
        --preview) TARGET_BRANCH="dev" ;;
        *) echo "Unknown flag: $arg (expected --secrets and/or --preview)"; exit 1 ;;
    esac
done

echo "🚀 Deploying to Cloudflare Pages (${TARGET_BRANCH} = $([ "$TARGET_BRANCH" = main ] && echo production || echo preview))"
echo "=================================="
echo ""

# Guard: deploy what git has, not half-edited local state.
if [ -n "$(git status --porcelain -- .)" ]; then
    echo "⚠️  dashboard/ has uncommitted changes:"
    git status --porcelain -- . | sed 's/^/    /'
    echo "   Commit or stash them first (the deploy should match a commit)."
    exit 1
fi

# Step 1: clean install so the pinned wrangler from the lockfile is used.
echo "📦 Step 1/3: npm ci..."
npm ci
echo ""

# Step 2: Build
echo "🔨 Step 2/3: Building project..."
npm run build
echo "✅ Build complete."
echo ""

# Optional: upload production Function secrets (rotation only — Pages keeps
# previously uploaded secrets, so the default deploy never re-sends them).
if [ "$UPLOAD_SECRETS" = "1" ]; then
    if [ "$TARGET_BRANCH" != "main" ]; then
        echo "⚠️  --secrets only targets the production environment; drop --preview."
        exit 1
    fi
    if [ ! -f "$PRODUCTION_SECRETS_FILE" ]; then
        echo "⚠️  Error: $PRODUCTION_SECRETS_FILE not found. Cannot upload secrets."
        exit 1
    fi
    echo "🔒 Uploading secrets from $PRODUCTION_SECRETS_FILE..."
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^\s*# ]] || [[ -z "$line" ]]; then
            continue
        fi
        KEY=$(echo "$line" | cut -d '=' -f 1)
        VALUE=$(echo "$line" | cut -d '=' -f 2-)
        echo "   - Uploading secret: $KEY"
        echo "$VALUE" | npx wrangler pages secret put "$KEY"
    done < "$PRODUCTION_SECRETS_FILE"
    echo "✅ Secrets uploaded."
    echo ""
fi

# Step 3: Deploy to Pages
# --branch=main promotes to the production environment (custom domain +
# production secrets); --branch=dev (via --preview) lands in the preview
# environment at a stable dev.<project>.pages.dev alias, which has no
# ClickHouse vars, so every endpoint serves the deterministic mocks.
echo "📤 Step 3/3: Deploying to Cloudflare Pages..."
npx wrangler pages deploy dist --branch="$TARGET_BRANCH" --commit-hash="$(git rev-parse HEAD)"
echo ""

if [ "$TARGET_BRANCH" = "main" ]; then
    echo "🩺 Post-deploy probe (X-Data-Source should be 'live'):"
    curl -sI "https://mylife-in-data.com/api/system/health" | grep -i 'x-data-source' || true
fi

echo "🎉 Deployment complete!"
echo ""
