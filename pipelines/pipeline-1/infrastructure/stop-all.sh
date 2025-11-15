#!/bin/bash
# stop-all.sh - Stop entire data platform

set -e

echo "Stopping Data Platform..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stop in reverse order
(cd "$SCRIPT_DIR/clickhouse" && docker-compose down)
(cd "$SCRIPT_DIR/airflow" && docker-compose down)
(cd "$SCRIPT_DIR/kafka" && docker-compose down)
(cd "$SCRIPT_DIR/storage" && docker-compose down)

echo "Data Platform Stopped!"