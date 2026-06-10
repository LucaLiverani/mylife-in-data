#!/usr/bin/env bash
# dev_clean.sh — wipe the dev warehouse sandbox (dev_silver + dev_gold).
#
# Dev views accumulate: prune_orphaned_views.sh only reconciles the prod
# silver/gold databases, so renamed/deleted models leave orphans in dev_*
# forever. This drops and recreates both dev databases (views only; nothing
# of value lives there) for a clean `dbt build --target dev`.
#
# Run on the host whose warehouse you want to clean (VM via `make dev-clean`,
# or the laptop against the local stack). Uses admin creds from
# infrastructure/.env.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "$REPO_ROOT/infrastructure/.env"; set +a

CH_URL="${CLICKHOUSE_URL:-http://${CLICKHOUSE_DDL_HOST:-localhost}:${CLICKHOUSE_HTTP_PORT:-8123}}"

run_sql() {
    curl -fsS --max-time 30 -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        "$CH_URL" --data-binary "$1"
}

for db in dev_silver dev_gold; do
    echo "→ Dropping + recreating ${db}..."
    run_sql "DROP DATABASE IF EXISTS ${db}"
    run_sql "CREATE DATABASE IF NOT EXISTS ${db}"
done

# Recreating the databases drops the dev user's pre-existing grants' targets;
# grants are on the database NAME, so they survive the drop/recreate.
echo "✓ Dev sandbox clean. Rebuild with: make dbt-dev"
