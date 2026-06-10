#!/usr/bin/env bash
# bootstrap_dev_user.sh — create/refresh the scoped `dbt_dev` ClickHouse user.
#
# NOT part of apply.sh: users and grants cannot live in committed DDL files in
# a public repo (the password would be in the SQL), so this is runtime SQL
# with the password injected from env. Idempotent: CREATE IF NOT EXISTS plus
# an ALTER to converge the password, and GRANTs are additive.
#
# The user is a WRITE-safety boundary, not a confidentiality one: SELECT on
# bronze is SELECT on the full personal history. It can read the prod layers,
# can only write inside dev_silver/dev_gold, and has no access to auth.*.
#
# Env (from infrastructure/.env):
#   CLICKHOUSE_USER / CLICKHOUSE_PASSWORD   admin connection (runs the DDL)
#   CLICKHOUSE_DBT_DEV_USER                 defaults to dbt_dev
#   CLICKHOUSE_DBT_DEV_PASSWORD             REQUIRED, non-empty
#   CLICKHOUSE_DDL_HOST / CLICKHOUSE_HTTP_PORT / CLICKHOUSE_URL  as apply.sh
#
# Usage (on the VM or against a local stack, from the repo root):
#   set -a; source infrastructure/.env; set +a
#   CLICKHOUSE_DDL_HOST=localhost bash warehouse/ddl/bootstrap_dev_user.sh

set -euo pipefail

CH_USER="${CLICKHOUSE_USER:-default}"
CH_PASS="${CLICKHOUSE_PASSWORD:-}"
CH_HOST="${CLICKHOUSE_DDL_HOST:-localhost}"
CH_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8123}"
CH_URL="${CLICKHOUSE_URL:-http://${CH_HOST}:${CH_HTTP_PORT}}"

DEV_USER="${CLICKHOUSE_DBT_DEV_USER:-dbt_dev}"
DEV_PASS="${CLICKHOUSE_DBT_DEV_PASSWORD:-}"

if [ -z "$DEV_PASS" ]; then
    echo "ERROR: CLICKHOUSE_DBT_DEV_PASSWORD must be set (add it to infrastructure/.env)." >&2
    exit 1
fi

run_sql() {
    local stmt="$1"
    if ! curl -fsS --max-time 30 -u "${CH_USER}:${CH_PASS}" "$CH_URL" --data-binary "$stmt" ; then
        echo "ERROR: statement failed: ${stmt:0:90}…" >&2
        exit 1
    fi
}

echo "Bootstrapping ClickHouse dev user '${DEV_USER}' on ${CH_URL}"

# Resource caps so a runaway dev query cannot starve the (small) VM.
run_sql "CREATE USER IF NOT EXISTS ${DEV_USER} IDENTIFIED BY '${DEV_PASS}'
         SETTINGS max_memory_usage = 4000000000, max_execution_time = 120"
# Converge the password on re-runs (CREATE IF NOT EXISTS won't update it).
run_sql "ALTER USER ${DEV_USER} IDENTIFIED BY '${DEV_PASS}'"

# Read the prod layers (views are INVOKER-default, so the whole chain down to
# bronze needs SELECT). Deliberately NOTHING on auth.*.
run_sql "GRANT SELECT ON bronze.* TO ${DEV_USER}"
run_sql "GRANT SELECT ON silver.* TO ${DEV_USER}"
run_sql "GRANT SELECT ON gold.* TO ${DEV_USER}"

# Full control inside the dev sandbox only. Explicit per-database grants: the
# pinned clickhouse-server 24.8 predates 24.10 wildcard (dev_*.*) grants.
# DROP covers DROP DATABASE/TABLE/VIEW within the named database; CREATE
# DATABASE covers dbt-clickhouse's CREATE DATABASE IF NOT EXISTS probe.
for db in dev_silver dev_gold; do
    run_sql "GRANT CREATE DATABASE, CREATE TABLE, CREATE VIEW, DROP, SELECT, INSERT, ALTER, TRUNCATE ON ${db}.* TO ${DEV_USER}"
done

echo "Dev user '${DEV_USER}' ready: SELECT on bronze/silver/gold, full control on dev_silver/dev_gold, no auth.*."
