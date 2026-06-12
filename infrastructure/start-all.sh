#!/bin/bash
# start-all.sh — Boot the data platform.
#
# Stack (5 services): Redpanda (streaming) → ClickHouse (warehouse)
#                     → Dagster (orchestration) → monitoring (Prometheus + Grafana)
#                     → Umami (web analytics).
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
for svc in clickhouse dagster monitoring redpanda umami; do
    ln -sf ../../.env "$COMPOSE_DIR/$svc/.env"
done

echo
echo "[1/5] Streaming (Redpanda)..."
(cd "$COMPOSE_DIR/redpanda" && docker compose up -d)
sleep 15
echo "      Ensuring topics exist..."
# Redpanda transports exactly one signal: the real-time Spotify "now playing"
# stream (producer → spotify.player.current → ClickHouse Kafka engine), plus
# its dead-letter sibling for events that fail the producer-side JSON Schema
# contract (spotify.player.current.dlq → bronze.spotify_player_current_dlq).
# Every other source is a direct batch INSERT into bronze, so no other topic
# is needed. Do NOT re-add the legacy spotify.tracks.raw / spotify.artist_ids /
# spotify.artists.raw / google.*.raw topics — they were never consumed and
# only reappeared on each redeploy.
docker exec redpanda rpk topic create \
    spotify.player.current \
    -p 3 -r 1 -c retention.ms=604800000 2>/dev/null || true
docker exec redpanda rpk topic create \
    spotify.player.current.dlq \
    -p 1 -r 1 -c retention.ms=604800000 2>/dev/null || true

echo
echo "[2/5] Warehouse (ClickHouse)..."
(cd "$COMPOSE_DIR/clickhouse" && docker compose up -d)
sleep 10

echo "      Applying ClickHouse DDL..."
# Source env so apply.sh sees CLICKHOUSE_USER / CLICKHOUSE_PASSWORD.
set -a; source "$SCRIPT_DIR/.env"; set +a
CLICKHOUSE_DDL_HOST=localhost bash "$SCRIPT_DIR/../warehouse/ddl/apply.sh" || \
    echo "      (DDL apply failed — check ClickHouse logs)"

echo
echo "[3/5] Orchestration (Dagster)..."
# Dagster image is built from a local Dockerfile (not on Docker Hub).
# --build is a no-op when the image is fresh, builds on first run / Dockerfile changes.
# spotify-current-producer is gated behind the `producer` compose profile —
# only started on the VM (DAGSTER_SCHEDULES_ENABLED=1). The laptop runs
# Dagster without producer so it doesn't compete with the VM's continuous
# polling of Spotify's currently-playing endpoint.
DAGSTER_COMPOSE_PROFILES=()
if [ "${DAGSTER_SCHEDULES_ENABLED:-0}" = "1" ]; then
    DAGSTER_COMPOSE_PROFILES+=(--profile producer)
    echo "      Schedules enabled — starting spotify-current-producer."
else
    echo "      Schedules disabled (DAGSTER_SCHEDULES_ENABLED!=1) — skipping spotify-current-producer."
fi
(cd "$COMPOSE_DIR/dagster" && docker compose "${DAGSTER_COMPOSE_PROFILES[@]}" up -d --build)
sleep 10

echo
echo "[4/5] Monitoring (Prometheus + Grafana + exporters)..."
# Alertmanager is gated behind the `alerting` compose profile — only started
# where ALERTING_ENABLED=1 (the VM). On the laptop, alert rules still
# evaluate and render in Grafana; there is just no delivery channel.
MONITORING_COMPOSE_PROFILES=()
if [ "${ALERTING_ENABLED:-0}" = "1" ]; then
    MONITORING_COMPOSE_PROFILES+=(--profile alerting)
    echo "      Alerting enabled — starting Alertmanager."
else
    echo "      Alerting disabled (ALERTING_ENABLED!=1) — skipping Alertmanager."
fi
(cd "$COMPOSE_DIR/monitoring" && docker compose "${MONITORING_COMPOSE_PROFILES[@]}" up -d)
sleep 5

echo
echo "[5/5] Web analytics (Umami)..."
(cd "$COMPOSE_DIR/umami" && docker compose up -d)
sleep 5

DAGSTER_PORT="${DAGSTER_PORT:-$(grep -E '^DAGSTER_PORT=' "$COMPOSE_DIR/dagster/.env" 2>/dev/null | cut -d= -f2)}"
DAGSTER_PORT="${DAGSTER_PORT:-3000}"
UMAMI_PORT="${UMAMI_PORT:-3002}"

echo
echo "Data Platform Started."
echo
echo "Access URLs (login: see compose/*/.env where applicable):"
echo "   Dagster UI:        http://localhost:${DAGSTER_PORT}"
echo "   Redpanda Console:  http://localhost:8090"
echo "   ClickHouse HTTP:   http://localhost:8123"
echo "   ClickHouse Native (TCP): localhost:9200"
echo "   Grafana:           http://localhost:3001"
echo "   Umami:             http://localhost:${UMAMI_PORT}"
echo "   Prometheus:        http://localhost:9090"
echo
