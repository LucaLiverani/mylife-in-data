#!/usr/bin/env bash
# sync_tokens_from_vm.sh — Pull Google OAuth tokens from VM ClickHouse to the laptop.
#
# The VM is the single writer for auth.google_tokens; the laptop runs with
# MYLIFE_TOKEN_WRITER=0 and pulls a fresh snapshot on demand whenever it needs
# to run a Google-backed asset or script locally.
#
# Reads:
#   dashboard/.env.production — CLICKHOUSE_HOST/USER/PASSWORD + CF Access creds
#                                (already used by the deployed Pages Functions)
#   infrastructure/.env       — local CLICKHOUSE_USER / CLICKHOUSE_PASSWORD
#
# Writes:
#   laptop's auth.google_tokens — via `docker exec clickhouse clickhouse-client`
#
# Usage:
#   ./scripts/sync_tokens_from_vm.sh                # pull both scope groups
#   ./scripts/sync_tokens_from_vm.sh --dry-run      # show rows, don't insert
#
# Requires: curl, docker (with a running `clickhouse` container locally).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_ENV="$REPO_ROOT/dashboard/.env.production"
LOCAL_ENV="$REPO_ROOT/infrastructure/.env"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

if [ ! -f "$DASHBOARD_ENV" ]; then
    echo "ERROR: $DASHBOARD_ENV not found." >&2
    echo "       This file holds VM ClickHouse credentials and the CF Access service token." >&2
    exit 1
fi
if [ ! -f "$LOCAL_ENV" ]; then
    echo "ERROR: $LOCAL_ENV not found." >&2
    exit 1
fi

# Pull VM creds. The dashboard env's CLICKHOUSE_HOST is the tunneled URL
# (e.g., https://clickhouse.<DOMAIN>); auth happens via Basic + CF Access.
# shellcheck disable=SC1090
set -a; source "$DASHBOARD_ENV"; set +a

VM_CH_HOST="${CLICKHOUSE_HOST:?CLICKHOUSE_HOST not set in dashboard/.env.production}"
VM_CH_USER="${CLICKHOUSE_USER:?CLICKHOUSE_USER not set in dashboard/.env.production}"
VM_CH_PASS="${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD not set in dashboard/.env.production}"
CF_ID="${CF_ACCESS_CLIENT_ID:?CF_ACCESS_CLIENT_ID not set in dashboard/.env.production}"
CF_SECRET="${CF_ACCESS_CLIENT_SECRET:?CF_ACCESS_CLIENT_SECRET not set in dashboard/.env.production}"

# Pull local creds (separate set; the laptop's ClickHouse may have its own).
LOCAL_CH_USER="$(grep -E '^CLICKHOUSE_USER=' "$LOCAL_ENV" | head -n1 | cut -d= -f2-)"
LOCAL_CH_PASS="$(grep -E '^CLICKHOUSE_PASSWORD=' "$LOCAL_ENV" | head -n1 | cut -d= -f2-)"
if [ -z "$LOCAL_CH_USER" ] || [ -z "$LOCAL_CH_PASS" ]; then
    echo "ERROR: Could not read local CLICKHOUSE_USER/PASSWORD from $LOCAL_ENV" >&2
    exit 1
fi

QUERY='SELECT account_email, scope_group, refresh_token, access_token, expires_at, scopes, issued_at FROM auth.google_tokens FINAL FORMAT JSONEachRow'

echo "→ Pulling auth.google_tokens from VM ($VM_CH_HOST)..."
TOKENS_JSON="$(curl -fsS \
    -X POST \
    -u "$VM_CH_USER:$VM_CH_PASS" \
    -H "CF-Access-Client-Id: $CF_ID" \
    -H "CF-Access-Client-Secret: $CF_SECRET" \
    -H 'Content-Type: text/plain' \
    --data-binary "$QUERY" \
    "$VM_CH_HOST/?database=auth")"

ROW_COUNT=$(printf '%s\n' "$TOKENS_JSON" | grep -c '^{' || true)
if [ "$ROW_COUNT" -eq 0 ]; then
    echo "WARNING: VM returned zero rows. Has bootstrap_google_auth.py been run on the VM?" >&2
    exit 2
fi
echo "  got $ROW_COUNT row(s)."

if [ "$DRY_RUN" -eq 1 ]; then
    echo "--- DRY RUN: rows that would be inserted into laptop auth.google_tokens ---"
    printf '%s\n' "$TOKENS_JSON"
    exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -q '^clickhouse$'; then
    echo "ERROR: local clickhouse container is not running. Start it with infrastructure/start-all.sh." >&2
    exit 1
fi

echo "→ Inserting into laptop auth.google_tokens..."
printf '%s\n' "$TOKENS_JSON" | docker exec -i clickhouse clickhouse-client \
    --user "$LOCAL_CH_USER" \
    --password "$LOCAL_CH_PASS" \
    --query "INSERT INTO auth.google_tokens FORMAT JSONEachRow"

echo "→ Verifying laptop row count per scope group..."
docker exec clickhouse clickhouse-client \
    --user "$LOCAL_CH_USER" \
    --password "$LOCAL_CH_PASS" \
    --query "SELECT scope_group, count() AS rows, max(issued_at) AS newest FROM auth.google_tokens FINAL GROUP BY scope_group FORMAT PrettyCompact"

echo "Done. Laptop tokens now mirror VM as of $(date -u +%Y-%m-%dT%H:%M:%SZ)."
