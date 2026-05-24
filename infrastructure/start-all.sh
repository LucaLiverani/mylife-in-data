#!/bin/bash
# start-all.sh — Boot the data platform.
#
# Stack (4 services): Redpanda (streaming) → ClickHouse (warehouse)
#                     → Dagster (orchestration) → monitoring (Prometheus + Grafana).
# Object storage uses Cloudflare R2 (out of compose). MinIO was dropped May 2026.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

echo "Starting Data Platform..."

if ! docker network inspect data-platform-network >/dev/null 2>&1; then
    echo "Creating shared network..."
    docker network create data-platform-network
fi

# Ensure each service's .env is a symlink to the consolidated infrastructure/.env.
# Idempotent: ln -sf overwrites any existing link/file at the destination.
for svc in clickhouse dagster monitoring redpanda; do
    ln -sf ../../.env "$COMPOSE_DIR/$svc/.env"
done

echo
echo "[1/4] Streaming (Redpanda)..."
(cd "$COMPOSE_DIR/redpanda" && docker compose up -d)
sleep 15
echo "      Ensuring topics exist..."
docker exec redpanda rpk topic create \
    spotify.tracks.raw spotify.player.current spotify.artist_ids spotify.artists.raw \
    google.youtube.raw google.maps.raw \
    -p 3 -r 1 -c retention.ms=604800000 2>/dev/null || true

echo
echo "[2/4] Warehouse (ClickHouse)..."
(cd "$COMPOSE_DIR/clickhouse" && docker compose up -d)
sleep 10

echo "      Applying ClickHouse DDL..."
# Source env so apply.sh sees CLICKHOUSE_USER / CLICKHOUSE_PASSWORD.
set -a; source "$SCRIPT_DIR/.env"; set +a
CLICKHOUSE_DDL_HOST=localhost bash "$SCRIPT_DIR/../warehouse/ddl/apply.sh" || \
    echo "      (DDL apply failed — check ClickHouse logs)"

echo
echo "[3/4] Orchestration (Dagster)..."
# Dagster image is built from a local Dockerfile (not on Docker Hub).
# --build is a no-op when the image is fresh, builds on first run / Dockerfile changes.
(cd "$COMPOSE_DIR/dagster" && docker compose up -d --build)
sleep 10

echo
echo "[4/4] Monitoring (Prometheus + Grafana)..."
(cd "$COMPOSE_DIR/monitoring" && docker compose up -d)
sleep 5

DAGSTER_PORT="${DAGSTER_PORT:-$(grep -E '^DAGSTER_PORT=' "$COMPOSE_DIR/dagster/.env" 2>/dev/null | cut -d= -f2)}"
DAGSTER_PORT="${DAGSTER_PORT:-3000}"

echo
echo "Data Platform Started."
echo
echo "Access URLs (login: see compose/*/.env where applicable):"
echo "   Dagster UI:        http://localhost:${DAGSTER_PORT}"
echo "   Redpanda Console:  http://localhost:8090"
echo "   ClickHouse HTTP:   http://localhost:8123"
echo "   ClickHouse Native: http://localhost:9200"
echo "   Grafana:           http://localhost:3001"
echo "   Prometheus:        http://localhost:9090"
echo
