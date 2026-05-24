#!/usr/bin/env bash
# warehouse/ddl/apply.sh — run every *.sql in this directory against the
# ClickHouse HTTP endpoint, in lexical order. Idempotent (all files use
# CREATE IF NOT EXISTS).
#
# ClickHouse's plain HTTP interface accepts one statement per request, so we
# split each file on `;` and POST each statement separately.
#
# Reads CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_HTTP_PORT from env
# (defaulted to the docker-compose values). If invoked from outside compose,
# point CLICKHOUSE_URL at the host's HTTP endpoint.

set -euo pipefail

DDL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CH_USER="${CLICKHOUSE_USER:-default}"
CH_PASS="${CLICKHOUSE_PASSWORD:-}"
CH_HOST="${CLICKHOUSE_DDL_HOST:-localhost}"
CH_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-8123}"
CH_URL="${CLICKHOUSE_URL:-http://${CH_HOST}:${CH_HTTP_PORT}}"

echo "Applying ClickHouse DDL from ${DDL_DIR}"
echo "  → ${CH_URL} (user=${CH_USER})"

# Splits a file on `;` boundaries, strips comments and empty fragments, then
# POSTs each remaining statement. Python is already a dep; using it avoids
# fragile awk/sed escaping for multi-line CREATE TABLE blocks.
run_sql_file() {
    local sql_file="$1"
    python3 - "$sql_file" "$CH_URL" "$CH_USER" "$CH_PASS" <<'PY'
import sys
import urllib.request
import base64
import re

path, url, user, password = sys.argv[1:5]
with open(path, encoding="utf-8") as fh:
    raw = fh.read()

# Strip --line and /* block */ comments before splitting.
raw = re.sub(r"--[^\n]*", "", raw)
raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)

statements = [s.strip() for s in raw.split(";") if s.strip()]
auth = base64.b64encode(f"{user}:{password}".encode()).decode()

for stmt in statements:
    req = urllib.request.Request(
        url,
        data=stmt.encode("utf-8"),
        headers={"Authorization": f"Basic {auth}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"DDL failed in {path}:\n{stmt[:120]}…\n→ {body}")
PY
}

for sql_file in $(ls "${DDL_DIR}"/*.sql | sort); do
    echo "  • $(basename "${sql_file}")"
    run_sql_file "${sql_file}"
done

echo "ClickHouse DDL applied."
