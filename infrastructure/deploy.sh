#!/usr/bin/env bash
# deploy.sh — Run on the VM to apply the latest deploy branch.
#
# Triggered from the laptop by `make deploy-vm`. Design doc: docs/DEPLOY.md.
#
# Flow:
#   1. refuse to run on a dirty worktree (fail loudly, no silent aborts)
#   2. resolve BEFORE: $1 (explicit oldrev, also used by the self re-exec)
#      > .last_deploy_rev (last SUCCESSFUL deploy) > current HEAD
#   3. pull the deploy branch, then re-exec the freshly pulled copy of this
#      script so new deploy logic applies to the deploy that ships it
#   4. build the Dagster image only if dependencies changed
#   5. VALIDATION GATE in a throwaway container (dbt parse, then dagster
#      definitions validate) — on failure, roll the worktree back to BEFORE
#      and abort BEFORE anything is applied or recreated (the repo is
#      bind-mounted into the running containers, so broken code on disk
#      would go live on any container restart)
#   6. apply ClickHouse DDL (idempotent) + prune orphaned dbt views
#   7. selectively recreate compose services based on the BEFORE..AFTER diff
#   8. if transformations/ or warehouse/ddl/ changed, launch dbt_build_job so
#      deployed models go live now, not at the 09:00 UTC schedule
#   9. health checks, then record HEAD in .last_deploy_rev
#
# .last_deploy_rev is written ONLY on success: a mid-deploy failure leaves it
# at the last good rev, so simply re-running the deploy retries the whole
# changed range instead of exiting 0 with "nothing to deploy".
#
# Exit codes: 0 = success (no changes is success), non-zero = a step failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"
STATE_FILE="$REPO_ROOT/.last_deploy_rev"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
cd "$REPO_ROOT"

# ── Dirty-worktree guard ──────────────────────────────────────────────────
# Gitignored runtime state (tokens/, transformations/target/, profiles.yml,
# .last_deploy_rev) never shows up here; anything that does is a real stray
# edit that would make `git pull --ff-only` abort cryptically further down.
if [ -n "$(git status --porcelain)" ]; then
    echo "✗ Worktree is dirty — refusing to deploy. Offending paths:"
    git status --porcelain | sed 's/^/    /'
    echo "  Commit, stash, or remove them on the VM, then re-run."
    exit 1
fi

# ── Determine BEFORE ──────────────────────────────────────────────────────
if [ -n "${1:-}" ]; then
    BEFORE="$1"
elif [ -f "$STATE_FILE" ]; then
    BEFORE="$(cat "$STATE_FILE")"
else
    BEFORE="$(git rev-parse HEAD)"
fi

# ── Pull, then re-exec the freshly pulled script ──────────────────────────
# Passing $BEFORE as $1 makes the second pass skip this block, so the exec
# cannot loop. Bare-repo post-receive hooks that already updated the worktree
# can keep calling `deploy.sh $oldrev` directly, as before.
if [ -z "${1:-}" ]; then
    echo "→ git pull origin ${DEPLOY_BRANCH}..."
    git fetch origin "$DEPLOY_BRANCH"
    git checkout "$DEPLOY_BRANCH" 2>/dev/null \
        || git checkout -b "$DEPLOY_BRANCH" --track "origin/$DEPLOY_BRANCH"
    git pull --ff-only origin "$DEPLOY_BRANCH"
    exec "$REPO_ROOT/infrastructure/deploy.sh" "$BEFORE"
fi

AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
    echo "✓ Already at $AFTER — nothing to deploy."
    echo "$AFTER" > "$STATE_FILE"
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

# Source env early — DAGSTER_SCHEDULES_ENABLED, ports and CH creds are used
# by several steps below.
set -a; source "$SCRIPT_DIR/.env"; set +a

# ── Service-level restart decisions ───────────────────────────────────────
# The Dagster image bakes ONLY pip deps (the repo and the dbt project are
# bind mounts, dagster.yaml/workspace.yaml are bind-mounted over the baked
# copies), so a rebuild is needed only when the dependency surface changes.
# Everything else is recreate-only.

RESTART_REDPANDA=0
RESTART_CLICKHOUSE=0
RESTART_DAGSTER=0
RESTART_MONITORING=0
RESTART_UMAMI=0
DAGSTER_FORCE_BUILD=0

if changed_in 'infrastructure/compose/redpanda/'; then RESTART_REDPANDA=1; fi
if changed_in 'infrastructure/compose/clickhouse/'; then RESTART_CLICKHOUSE=1; fi
if changed_in 'infrastructure/compose/dagster/'; then RESTART_DAGSTER=1; fi
if changed_in 'infrastructure/compose/monitoring/'; then RESTART_MONITORING=1; fi
if changed_in 'infrastructure/compose/umami/'; then RESTART_UMAMI=1; fi

if changed_in 'orchestration/' \
   || changed_in 'ingestion/' \
   || changed_in 'transformations/'; then
    RESTART_DAGSTER=1
fi

if changed_in 'infrastructure/compose/dagster/Dockerfile' \
   || changed_in 'pyproject.toml' \
   || changed_in 'uv.lock' \
   || changed_in 'requirements'; then
    RESTART_DAGSTER=1
    DAGSTER_FORCE_BUILD=1
fi

# ── Build (only when deps changed, or the image is missing entirely) ──────
if ! docker image inspect mylife-dagster:latest >/dev/null 2>&1; then
    DAGSTER_FORCE_BUILD=1
fi
if [ "$DAGSTER_FORCE_BUILD" = "1" ]; then
    echo "→ Building Dagster image (dependency surface changed)..."
    (cd "$COMPOSE_DIR/dagster" && docker compose build dagster-webserver)
fi

# ── Validation gate ───────────────────────────────────────────────────────
# Runs against the image we are about to deploy, with the post-pull code.
# `dbt parse` MUST stay a separate failing step: `dagster definitions
# validate` exits 0 with a broken dbt model (the import-time bootstrap in
# orchestration/dagster/assets/dbt.py swallows the parse failure and silently
# drops all dbt assets). transformations/ is mounted RW on purpose so the
# parse refreshes the real manifest the recreated containers will load.
[ -f "$REPO_ROOT/transformations/profiles.yml" ] \
    || cp "$REPO_ROOT/transformations/profiles.yml.example" "$REPO_ROOT/transformations/profiles.yml"

echo "→ Validation gate (dbt parse + dagster definitions validate)..."
if ! docker run --rm --network none \
    -v "$REPO_ROOT":/opt/dagster/repo:ro \
    -v "$REPO_ROOT/transformations":/opt/dagster/transformations \
    -e DAGSTER_HOME=/tmp/dagster_home \
    -e DAGSTER_SCHEDULES_ENABLED=1 \
    -w /opt/dagster/repo \
    mylife-dagster:latest \
    bash -c 'mkdir -p /tmp/dagster_home \
        && dbt parse --project-dir /opt/dagster/transformations --profiles-dir /opt/dagster/transformations \
        && dagster definitions validate -f orchestration/dagster/definitions.py'
then
    echo "✗ Validation failed — rolling the worktree back to $BEFORE."
    echo "  (The repo is bind-mounted into the running containers; leaving the"
    echo "   broken commit on disk would load it on any container restart.)"
    git reset --hard "$BEFORE"
    exit 1
fi
echo "✓ Validation passed."

# ── Apply DDL (cheap + idempotent) ────────────────────────────────────────
echo "→ Applying ClickHouse DDL..."
CLICKHOUSE_DDL_HOST=localhost bash "$REPO_ROOT/warehouse/ddl/apply.sh"

# ── Reconcile dbt views (drop orphans left by deleted models) ─────────────
# DDL only ever CREATEs, so a deleted dbt model leaves its view behind in CH.
# This drops any gold/silver VIEW that is neither a current dbt model nor a
# DDL-created view. View-only + gold/silver-only, so raw bronze tables and the
# Dagster/DDL trip tables are never touched. Never fails the deploy.
echo "→ Pruning orphaned dbt views..."
CLICKHOUSE_DDL_HOST=localhost bash "$REPO_ROOT/warehouse/ddl/prune_orphaned_views.sh" || true

# ── Recreate what changed ─────────────────────────────────────────────────
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
    echo "→ Recreating Dagster (and producer if schedules on)..."
    (cd "$COMPOSE_DIR/dagster" && docker compose "${DAGSTER_PROFILES[@]}" up -d --force-recreate)
fi
if [ "$RESTART_MONITORING" = "1" ]; then
    echo "→ Recreating monitoring (Prometheus + Grafana)..."
    (cd "$COMPOSE_DIR/monitoring" && docker compose up -d --force-recreate)
fi
if [ "$RESTART_UMAMI" = "1" ]; then
    # Isolated compose project — plain `up -d` only creates/updates the umami +
    # umami-postgres containers; it never touches the other stacks. No
    # --force-recreate, so an unchanged umami is a no-op.
    echo "→ Bringing up Umami..."
    ln -sf ../../.env "$COMPOSE_DIR/umami/.env"
    (cd "$COMPOSE_DIR/umami" && docker compose up -d)
fi

if [ "$RESTART_REDPANDA" = "0" ] \
   && [ "$RESTART_CLICKHOUSE" = "0" ] \
   && [ "$RESTART_DAGSTER" = "0" ] \
   && [ "$RESTART_MONITORING" = "0" ] \
   && [ "$RESTART_UMAMI" = "0" ]; then
    echo "→ No container restarts needed (only docs/scripts/dashboard changed)."
fi

# ── Close the dbt gap: deployed models go live now, not at 09:00 UTC ──────
# dbt_build_job only registers when DAGSTER_SCHEDULES_ENABLED=1 (laptop runs
# without it, and without the schedule there is no job to launch). The CLI
# loads definitions in-process from the bind mount and queues the run; the
# daemon dequeues it, and run_monitoring caps a wedged run, so fire-and-forget
# is safe.
if { changed_in 'transformations/' || changed_in 'warehouse/ddl/'; } \
   && [ "${DAGSTER_SCHEDULES_ENABLED:-0}" = "1" ]; then
    echo "→ Launching dbt_build_job (transformations/DDL changed)..."
    docker exec dagster-webserver \
        dagster job launch -j dbt_build_job -w /opt/dagster/workspace.yaml \
        || echo "⚠ dbt build launch failed — materialize mylife_dbt_assets from the Dagster UI."
fi

# ── Health checks ─────────────────────────────────────────────────────────
# A failed check aborts before .last_deploy_rev is written, so the next run
# retries the full range.
wait_http() {
    local url="$1" name="$2" tries="${3:-18}"
    local i
    for i in $(seq 1 "$tries"); do
        if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
            echo "  ✓ $name"
            return 0
        fi
        sleep 5
    done
    echo "  ✗ $name not responding at $url"
    return 1
}
echo "→ Health checks..."
wait_http "http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}/ping" "ClickHouse" 6
wait_http "http://localhost:${DAGSTER_PORT:-3000}/server_info" "Dagster webserver" 18

if changed_in 'dashboard/'; then
    echo "ℹ dashboard/ changed — it ships separately: CI deploys it on push to"
    echo "  main, or run dashboard/scripts/deploy-to-pages.sh from the laptop."
fi

echo "$AFTER" > "$STATE_FILE"
echo
echo "✓ Deploy complete. HEAD is now $AFTER."
docker ps --format 'table {{.Names}}\t{{.Status}}'
