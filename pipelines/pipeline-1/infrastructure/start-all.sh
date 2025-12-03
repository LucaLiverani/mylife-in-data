#!/bin/bash
# start-all.sh - Start entire data platform

set -e

echo "Starting Data Platform..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create shared network if it doesn't exist
if ! docker network inspect data-platform-network >/dev/null 2>&1; then
    echo "Creating shared network..."
    docker network create data-platform-network
fi

# Start storage (MinIO)
echo "Starting storage layer..."
(cd "$SCRIPT_DIR/storage" && docker-compose up -d)

# Wait for MinIO
echo "Waiting for MinIO to be ready..."
sleep 10

# Start Kafka
echo "Starting Kafka ecosystem..."
(cd "$SCRIPT_DIR/kafka" && docker-compose up -d)

# Wait for Kafka
echo "Waiting for Kafka to be ready..."
sleep 15

# Start Airflow
echo "Starting Airflow..."
(cd "$SCRIPT_DIR/airflow" && docker-compose up -d)
sleep 15

# Start ClickHouse
echo "Starting ClickHouse..."
(cd "$SCRIPT_DIR/clickhouse" && docker-compose up -d)
sleep 10

# Start Monitoring
echo "Starting Monitoring stack..."
(cd "$SCRIPT_DIR/monitoring" && docker-compose up -d)
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
# echo "View status: ./status.sh"
# echo "View logs:   ./logs.sh [storage|kafka|airflow] [service-name]"
# echo ""