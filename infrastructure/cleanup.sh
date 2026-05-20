#!/bin/bash
# cleanup.sh - Clean up old containers and optionally volumes

set -e

REMOVE_VOLUMES=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        *)
            echo "Usage: ./cleanup.sh [-v|--volumes]"
            echo "  -v, --volumes    Also remove volumes (⚠️  deletes all data)"
            exit 1
            ;;
    esac
done

echo "🧹 Cleaning up old containers..."

# Stop and remove containers by name (common conflicts)
CONTAINERS=(
    "minio"
    "minio-mc-init"
    "minio-init"
    "zookeeper"
    "kafka"
    "schema-registry"
    "kafka-ui"
    "kafka-connect"
    "airflow-webserver"
    "airflow-scheduler"
    "airflow-worker"
    "airflow-triggerer"
    "airflow-init"
    "airflow-postgres"
    "postgres"
    "airflow-redis"
    "redis"
    "airflow-flower"
    "statsd-exporter"
    "postgres-backup"
)

for container in "${CONTAINERS[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "  Removing container: $container"
        docker rm -f "$container" 2>/dev/null || true
    fi
done

# Remove containers from compose projects
echo ""
echo "Cleaning up docker-compose projects..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/compose"

if [ -d "$COMPOSE_DIR/storage" ]; then
    (cd "$COMPOSE_DIR/storage" && docker compose down)
fi

if [ -d "$COMPOSE_DIR/kafka" ]; then
    (cd "$COMPOSE_DIR/kafka" && docker compose down)
fi

if [ -d "$COMPOSE_DIR/airflow" ]; then
    (cd "$COMPOSE_DIR/airflow" && docker compose down)
fi

# Remove dangling containers
echo ""
echo "🗑️  Removing dangling containers..."
docker container prune -f

if [ "$REMOVE_VOLUMES" = true ]; then
    echo ""
    echo "⚠️  WARNING: Removing volumes will delete ALL data!"
    read -p "Are you absolutely sure? Type 'DELETE' to confirm: " -r
    echo
    
    if [[ $REPLY == "DELETE" ]]; then
        echo "Removing volumes..."

        if [ -d "$COMPOSE_DIR/storage" ]; then
            (cd "$COMPOSE_DIR/storage" && docker compose down -v)
        fi

        if [ -d "$COMPOSE_DIR/kafka" ]; then
            (cd "$COMPOSE_DIR/kafka" && docker compose down -v)
        fi

        if [ -d "$COMPOSE_DIR/airflow" ]; then
            (cd "$COMPOSE_DIR/airflow" && docker compose down -v)
        fi
        
        # Remove dangling volumes
        docker volume prune -f
        
        echo "✅ Volumes removed"
    else
        echo "❌ Volume removal cancelled"
    fi
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Next steps:"
echo "  1. Verify: docker ps -a"
echo "  2. Start platform: ./start-all.sh"