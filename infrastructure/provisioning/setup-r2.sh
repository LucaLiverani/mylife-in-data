#!/bin/bash
# setup-r2.sh — Provision a Cloudflare R2 bucket and wire credentials
# into infrastructure/.env. Run once per environment (laptop and VM).
#
# What this does:
#   1. Detects an authenticated wrangler (global install or dashboard/node_modules)
#   2. Looks up your Cloudflare account ID
#   3. Creates the R2 bucket (idempotent — survives re-runs)
#   4. Prints the dashboard URL to mint a bucket-scoped API token
#   5. Reads the pasted Access Key ID + Secret, updates infrastructure/.env
#
# What it does NOT do:
#   - Mint the S3-compatible API token itself. Wrangler doesn't support that
#     (it only handles bucket lifecycle). Token creation is a 30-second click
#     in the dashboard.
#
# Usage:
#   ./setup-r2.sh [bucket-name]   # default bucket: mylife-data-lake

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
INFRA_ENV="$INFRA_DIR/.env"

BUCKET="${1:-mylife-data-lake}"

# ── Locate wrangler ────────────────────────────────────────────────────────
if command -v wrangler >/dev/null 2>&1; then
    WRANGLER="wrangler"
elif [ -x "$REPO_ROOT/dashboard/node_modules/.bin/wrangler" ]; then
    WRANGLER="$REPO_ROOT/dashboard/node_modules/.bin/wrangler"
else
    cat <<EOF
ERROR: wrangler not found.
  - Install globally:  npm i -g wrangler
  - Or use the local one in dashboard/:  (cd dashboard && npm install)
EOF
    exit 1
fi

# ── Confirm auth ───────────────────────────────────────────────────────────
WHOAMI=$("$WRANGLER" whoami 2>&1 || true)
if echo "$WHOAMI" | grep -qiE "(not authenticated|please run)"; then
    echo "Not authenticated. Run:"
    echo "  $WRANGLER login"
    exit 1
fi

# Extract the 32-char account ID
ACCOUNT_ID=$(echo "$WHOAMI" | grep -oE '[a-f0-9]{32}' | head -1)
if [ -z "$ACCOUNT_ID" ]; then
    echo "Could not extract account ID from wrangler whoami output."
    echo "Paste your Cloudflare account ID manually (32 hex chars):"
    read -r ACCOUNT_ID
fi

ENDPOINT="https://${ACCOUNT_ID}.r2.cloudflarestorage.com"

echo
echo "Account ID: $ACCOUNT_ID"
echo "Endpoint:   $ENDPOINT"
echo "Bucket:     $BUCKET"
echo

# ── Create bucket (idempotent) ─────────────────────────────────────────────
echo "Creating bucket..."
if "$WRANGLER" r2 bucket create "$BUCKET" 2>&1; then
    echo "Bucket created."
else
    echo "(bucket likely already exists — continuing)"
fi
echo

# ── Mint token (manual step) ───────────────────────────────────────────────
TOKEN_URL="https://dash.cloudflare.com/${ACCOUNT_ID}/r2/api-tokens"
cat <<EOF
================================================================
Open this URL to mint a bucket-scoped R2 API token:

    $TOKEN_URL

In that page:
  - Click 'Create API Token'
  - Permission:     Object Read & Write
  - Specify bucket: $BUCKET
  - TTL:            Forever (or whatever you prefer)
  - Click 'Create API Token'

Copy the THREE values shown ONCE on the next page.
================================================================
EOF

read -p "Paste Access Key ID: " ACCESS_KEY_ID
read -s -p "Paste Secret Access Key: " SECRET_ACCESS_KEY
echo
echo

if [ -z "$ACCESS_KEY_ID" ] || [ -z "$SECRET_ACCESS_KEY" ]; then
    echo "Empty credential. Aborting without writing .env."
    exit 1
fi

# ── Bootstrap .env if missing ──────────────────────────────────────────────
if [ ! -f "$INFRA_ENV" ]; then
    echo "Creating $INFRA_ENV from .env.example..."
    cp "$INFRA_DIR/.env.example" "$INFRA_ENV"
    chmod 600 "$INFRA_ENV"
    echo "  ⚠ Remember to fill in non-R2 values (CLICKHOUSE_PASSWORD, etc.)."
fi

# ── Update R2_* keys in-place ──────────────────────────────────────────────
update_var() {
    local key="$1" value="$2"
    if grep -qE "^${key}=" "$INFRA_ENV"; then
        # Escape value for sed (forward slashes + ampersands)
        local esc=$(printf '%s\n' "$value" | sed 's/[\/&]/\\&/g')
        sed -i "s|^${key}=.*|${key}=${esc}|" "$INFRA_ENV"
    else
        echo "${key}=${value}" >> "$INFRA_ENV"
    fi
}

update_var R2_ACCOUNT_ID "$ACCOUNT_ID"
update_var R2_ACCESS_KEY_ID "$ACCESS_KEY_ID"
update_var R2_SECRET_ACCESS_KEY "$SECRET_ACCESS_KEY"
update_var R2_BUCKET "$BUCKET"

chmod 600 "$INFRA_ENV"

echo "R2 credentials written to $INFRA_ENV (chmod 600)."
echo
echo "Sanity check — uploading + deleting a 0-byte test object:"
TEST_KEY=".setup-r2-test-$(date +%s)"
if "$WRANGLER" r2 object put "$BUCKET/$TEST_KEY" --file=/dev/null >/dev/null 2>&1; then
    "$WRANGLER" r2 object delete "$BUCKET/$TEST_KEY" >/dev/null 2>&1 || true
    echo "  ✓ bucket round-trip works"
else
    echo "  ⚠ couldn't write to the bucket via wrangler. Token works for S3 API but"
    echo "    wrangler uses account creds — this isn't a blocker for your pipelines."
fi

echo
echo "Done."
