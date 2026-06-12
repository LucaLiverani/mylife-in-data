#!/bin/bash
# stop-all.sh — Stop the data platform (every stack start-all.sh starts).

set -e

echo "Stopping Data Platform..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

(cd "$COMPOSE_DIR/umami" && docker compose down)
# --profile alerting so the VM's profile-gated alertmanager is stopped too;
# harmless on the laptop where the profile was never started.
(cd "$COMPOSE_DIR/monitoring" && docker compose --profile alerting down)
# --profile producer so the VM's profile-gated spotify-current-producer is
# stopped too; harmless on the laptop where the profile was never started.
(cd "$COMPOSE_DIR/dagster" && docker compose --profile producer down)
(cd "$COMPOSE_DIR/clickhouse" && docker compose down)
(cd "$COMPOSE_DIR/redpanda" && docker compose down)

echo "Data Platform Stopped."
