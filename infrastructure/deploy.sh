#!/usr/bin/env bash
# deploy.sh — Run on the VM to apply the latest dev branch.
#
# Triggered from the laptop by `make deploy-vm` (which does
# `git push origin dev && ssh <VM> 'cd ~/mylife-in-data && ./infrastructure/deploy.sh'`).
#
# Steps:
#   1. record the current HEAD as BEFORE (unless $1 is passed — bare-repo hooks
#      can pass $oldrev directly)
#   2. git pull origin dev (no-op if a post-receive hook already updated the
#      worktree)
#   3. diff BEFORE..AFTER to figure out what actually changed
#   4. apply ClickHouse DDL (always — it's idempotent and cheap)
#   5. selectively rebuild + recreate compose services based on the diff
#
# Exit codes:
#   0 = success (no changes is success)
#   non-zero = a step failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"
cd "$REPO_ROOT"

# ── Determine BEFORE / AFTER ──────────────────────────────────────────────
BEFORE="${1:-$(git rev-parse HEAD)}"

if [ -z "${1:-}" ]; then
    echo "→ git pull origin dev..."
    git fetch origin dev
    git checkout dev
    git pull --ff-only origin dev
fi
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
    echo "✓ Already at $AFTER — nothing to deploy."
    exit 0
fi

echo "→ Diff $BEFORE..$AFTER:"
CHANGED="$(git diff --name-only "$BEFORE" "$AFTER")"
printf '%s\n' "$CHANGED" | sed 's/^/    /'

changed_in() {
    # Returns 0 if any changed path matches the given prefix.
    local prefix="$1"
    printf '%s\n' "$CHANGED" | grep -q "^$prefix" || return 1
}

# ── Apply DDL (cheap + idempotent) ────────────────────────────────────────
echo "→ Applying ClickHouse DDL..."
# Source env so apply.sh sees CH creds.
set -a; source "$SCRIPT_DIR/.env"; set +a
CLICKHOUSE_DDL_HOST=localhost bash "$REPO_ROOT/warehouse/ddl/apply.sh"

# ── Service-level restart decisions ───────────────────────────────────────
# Heuristics: anything that lives inside the Dagster image (orchestration,
# ingestion, transformations, dbt) or its build context (Dockerfile,
# pyproject, lockfile) requires a Dagster rebuild + recreate. Compose YAML
# changes also recreate. Pure docs/scripts/dashboard touches are no-ops on
# the VM side.

RESTART_REDPANDA=0
RESTART_CLICKHOUSE=0
RESTART_DAGSTER=0
RESTART_MONITORING=0
DAGSTER_FORCE_BUILD=0

if changed_in 'infrastructure/compose/redpanda/'; then RESTART_REDPANDA=1; fi
if changed_in 'infrastructure/compose/clickhouse/'; then RESTART_CLICKHOUSE=1; fi
if changed_in 'infrastructure/compose/dagster/'; then RESTART_DAGSTER=1; DAGSTER_FORCE_BUILD=1; fi
if changed_in 'infrastructure/compose/monitoring/'; then RESTART_MONITORING=1; fi

# Dagster image bakes in Python deps + dbt project. Anything in those trees
# means rebuild.
if changed_in 'orchestration/' \
   || changed_in 'ingestion/' \
   || changed_in 'transformations/' \
   || changed_in 'pyproject.toml' \
   || changed_in 'uv.lock' \
   || changed_in 'requirements'; then
    RESTART_DAGSTER=1
    DAGSTER_FORCE_BUILD=1
fi

# `dashboard/` ships to Cloudflare Pages from the laptop, not the VM.
# `scripts/`, `docs/`, top-level *.md → no VM-side container restart.

if [ "$RESTART_REDPANDA" = "1" ]; then
    echo "→ Recreating Redpanda..."
    (cd "$COMPOSE_DIR/redpanda" && docker compose up -d --force-recreate)
fi
if [ "$RESTART_CLICKHOUSE" = "1" ]; then
    echo "→ Recreating ClickHouse..."
    (cd "$COMPOSE_DIR/clickhouse" && docker compose up -d --force-recreate)
fi
if [ "$RESTART_DAGSTER" = "1" ]; then
    DAGSTER_PROFILES=()
    if [ "${DAGSTER_SCHEDULES_ENABLED:-0}" = "1" ]; then
        DAGSTER_PROFILES+=(--profile producer)
    fi
    if [ "$DAGSTER_FORCE_BUILD" = "1" ]; then
        echo "→ Rebuilding + recreating Dagster (and producer if schedules on)..."
        (cd "$COMPOSE_DIR/dagster" && docker compose "${DAGSTER_PROFILES[@]}" up -d --build --force-recreate)
    else
        echo "→ Recreating Dagster (no rebuild needed)..."
        (cd "$COMPOSE_DIR/dagster" && docker compose "${DAGSTER_PROFILES[@]}" up -d --force-recreate)
    fi
fi
if [ "$RESTART_MONITORING" = "1" ]; then
    echo "→ Recreating monitoring (Prometheus + Grafana)..."
    (cd "$COMPOSE_DIR/monitoring" && docker compose up -d --force-recreate)
fi

if [ "$RESTART_REDPANDA" = "0" ] \
   && [ "$RESTART_CLICKHOUSE" = "0" ] \
   && [ "$RESTART_DAGSTER" = "0" ] \
   && [ "$RESTART_MONITORING" = "0" ]; then
    echo "→ No container restarts needed (only docs/scripts/dashboard changed)."
fi

echo
echo "✓ Deploy complete. HEAD is now $AFTER."
docker ps --format 'table {{.Names}}\t{{.Status}}'
