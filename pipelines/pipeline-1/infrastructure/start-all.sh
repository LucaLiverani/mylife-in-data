#!/bin/bash
# start-all.sh - Start entire data platform

set -e

echo "Starting Data Platform..."

# Create shared network if it doesn't exist
if ! docker network inspect data-platform-network >/dev/null 2>&1; then
    echo "Creating shared network..."
    docker network create data-platform-network
fi

# Start storage (MinIO)
echo "Starting storage layer..."
cd storage && docker-compose up -d && cd ..

# Wait for MinIO
echo "Waiting for MinIO to be ready..."
sleep 10

# Start Kafka
echo "Starting Kafka ecosystem..."
cd kafka && docker-compose up -d && cd ..

# Wait for Kafka
echo "Waiting for Kafka to be ready..."
sleep 15
#
# Start Airflow
echo "Starting Airflow..."
cd airflow && docker-compose up -d && cd ..
sleep 15

echo ""
echo "Data Platform Started Successfully!"
echo ""
echo "Access URLs:"
echo "   Airflow UI:        http://localhost:8080"
echo "   MinIO Console:     http://localhost:9001"
echo "   Kafka UI:          http://localhost:8090"
echo "   Schema Registry:   http://localhost:8081"
echo ""
# echo "View status: ./status.sh"
# echo "View logs:   ./logs.sh [storage|kafka|airflow] [service-name]"
# echo ""