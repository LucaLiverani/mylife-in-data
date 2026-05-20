#!/bin/bash
# start-all.sh - Start entire data platform

set -e

echo "Starting Data Platform..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

if ! docker network inspect data-platform-network >/dev/null 2>&1; then
    echo "Creating shared network..."
    docker network create data-platform-network
fi

echo "Starting storage layer..."
(cd "$COMPOSE_DIR/storage" && docker compose up -d)

echo "Waiting for MinIO to be ready..."
sleep 10

echo "Starting Kafka ecosystem..."
(cd "$COMPOSE_DIR/kafka" && docker compose up -d)

echo "Waiting for Kafka to be ready..."
sleep 15

echo "Starting Airflow..."
(cd "$COMPOSE_DIR/airflow" && docker compose up -d)
sleep 15

echo "Starting ClickHouse..."
(cd "$COMPOSE_DIR/clickhouse" && docker compose up -d)
sleep 10

echo "Starting Monitoring stack..."
(cd "$COMPOSE_DIR/monitoring" && docker compose up -d)
sleep 10

echo ""
echo "Data Platform Started Successfully!"
echo ""
echo "Access URLs:"
echo "   Airflow UI:        http://localhost:8080"
echo "   MinIO Console:     http://localhost:9001"
echo "   Kafka UI:          http://localhost:8090"
echo "   Schema Registry:   http://localhost:8081"
echo "   ClickHouse HTTP:   http://localhost:8123"
echo "   ClickHouse Native: http://localhost:9200"
echo ""
echo "Monitoring URLs:"
echo "   Prometheus:        http://localhost:9090"
echo "   Grafana:           http://localhost:3001"
echo "   cAdvisor:          http://localhost:8082"
echo "   Node Exporter:     http://localhost:9100"
echo ""
