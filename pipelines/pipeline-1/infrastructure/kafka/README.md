# Kafka Setup

This directory contains the Docker Compose configuration for setting up a Kafka cluster.

The setup includes:
- Zookeeper
- Kafka Broker
- Schema Registry
- Kafka UI
- Kafka Connect

## Getting Started

### 1. Prerequisites

- Docker
- Docker Compose

### 2. Start the Services

You can start the Kafka cluster using the main `start-all.sh` script in the parent directory, or by running the following command in this directory:

```bash
docker-compose up -d
```

## Accessing Kafka

- **Kafka Broker**: `localhost:9093`
- **Schema Registry**: `http://localhost:8081`
- **Kafka UI**: `http://localhost:8090`
- **Kafka Connect**: `http://localhost:8083`
