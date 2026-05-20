#!/bin/bash
# stop-all.sh - Stop entire data platform

set -e

echo "Stopping Data Platform..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

# Stop in reverse order
(cd "$COMPOSE_DIR/monitoring" && docker compose down)
(cd "$COMPOSE_DIR/clickhouse" && docker compose down)
(cd "$COMPOSE_DIR/airflow" && docker compose down)
(cd "$COMPOSE_DIR/kafka" && docker compose down)
(cd "$COMPOSE_DIR/storage" && docker compose down)

echo "Data Platform Stopped!"
