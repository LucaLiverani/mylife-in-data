#!/bin/bash
# stop-all.sh - Stop entire data platform

set -e

echo "Stopping Data Platform..."

# Stop in reverse order
cd airflow && docker-compose down && cd ..
cd kafka && docker-compose down && cd ..
cd storage && docker-compose down && cd ..

echo "Data Platform Stopped!"