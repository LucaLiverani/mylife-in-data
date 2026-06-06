#!/usr/bin/env bash
# warehouse/ddl/prune_orphaned_views.sh — reconcile the warehouse to the dbt
# project by dropping orphaned views.
#
# A gold/silver object is dropped ONLY when ALL of these hold:
#   - it lives in the `gold` or `silver` database (never bronze),
#   - its engine is `View` (never a MergeTree table — so the Dagster/DDL trip
#     tables like silver.maps_trips and all raw bronze data are untouchable),
#   - it is NOT a current dbt model (transformations/models/{gold,silver}/*.sql),
#   - it is NOT a DDL-created view (e.g. silver.maps_activity_keyed in
#     warehouse/ddl/*.sql), which dbt models legitimately read from.
#
# i.e. it removes exactly the views a deleted dbt model leaves behind, and
# nothing else. Idempotent, logs every drop, and never fails the caller.
#
# Reads the same CH env vars as apply.sh (CLICKHOUSE_USER / _PASSWORD /
# _HTTP_PORT, CLICKHOUSE_DDL_HOST or CLICKHOUSE_URL).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CH_USER="${CLICKHOUSE_USER:-default}"
CH_PASS="${CLICKHOUSE_PASSWORD:-}"
CH_HOST="${CLICKHOUSE_DDL_HOST:-localhost}"
CH_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8123}"
CH_URL="${CLICKHOUSE_URL:-http://${CH_HOST}:${CH_HTTP_PORT}}"

python3 - "$REPO_ROOT" "$CH_URL" "$CH_USER" "$CH_PASS" <<'PY'
import sys, os, re, glob, base64, urllib.request, urllib.error

repo_root, url, user, password = sys.argv[1:5]
auth = base64.b64encode(f"{user}:{password}".encode()).decode()

def ch(query):
    req = urllib.request.Request(
        url, data=query.encode("utf-8"),
        headers={"Authorization": f"Basic {auth}"}, method="POST",
    )
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

# keep-set 1: current dbt models (filename = view name, folder = schema).
keep = set()
for layer in ("gold", "silver"):
    for f in glob.glob(os.path.join(repo_root, "transformations", "models", layer, "*.sql")):
        keep.add(f"{layer}.{os.path.basename(f)[:-4]}")

# Safety rail: an empty model set means a broken/partial checkout. Skip the
# prune entirely rather than risk dropping live views.
if not keep:
    print("  prune skipped: found 0 dbt model files (unexpected) — not dropping anything.")
    raise SystemExit(0)
n_models = len(keep)

# keep-set 2: DDL-created views (these are NOT dbt models but are real objects
# dbt models read from, e.g. silver.maps_activity_keyed).
view_re = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)", re.I)
n_ddl = 0
for f in glob.glob(os.path.join(repo_root, "warehouse", "ddl", "*.sql")):
    with open(f, encoding="utf-8") as fh:
        for db, name in view_re.findall(fh.read()):
            keep.add(f"{db}.{name}")
            n_ddl += 1

# Existing views in the dbt-managed schemas.
try:
    rows = ch(
        "SELECT database || '.' || name FROM system.tables "
        "WHERE database IN ('gold','silver') AND engine = 'View' "
        "ORDER BY 1 FORMAT TabSeparated"
    ).splitlines()
except (urllib.error.URLError, OSError) as e:
    print(f"  prune skipped: could not reach ClickHouse ({e}).")
    raise SystemExit(0)

dropped = []
for fqn in (r.strip() for r in rows):
    if not fqn or fqn in keep:
        continue
    try:
        ch(f"DROP VIEW IF EXISTS {fqn}")
        dropped.append(fqn)
        print(f"  dropped orphaned view {fqn}")
    except (urllib.error.URLError, OSError) as e:
        print(f"  WARN: could not drop {fqn}: {e}")

print(
    f"  prune complete: {len(dropped)} dropped, {len(rows)} views scanned, "
    f"{n_models} dbt models + {n_ddl} DDL views protected."
)
PY

exit 0
