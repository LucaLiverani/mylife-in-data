#!/bin/bash
# stop-all.sh — Stop the data platform.

set -e

echo "Stopping Data Platform..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

(cd "$COMPOSE_DIR/monitoring" && docker compose down)
(cd "$COMPOSE_DIR/dagster" && docker compose down)
(cd "$COMPOSE_DIR/clickhouse" && docker compose down)
(cd "$COMPOSE_DIR/redpanda" && docker compose down)

echo "Data Platform Stopped."
