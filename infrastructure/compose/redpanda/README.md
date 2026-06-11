# Redpanda (Kafka-compatible broker)

Single-node Redpanda + Console as a drop-in for the existing Kafka stack.

## Why

- Kafka API-compatible — existing producer and ClickHouse Kafka engine tables Just Work
- No JVM, no Zookeeper — ~1 GB RAM vs ~3 GB for Kafka + ZK + Schema Registry + Connect + UI
- Single binary, multi-arch (works on the ARM VM)
- Bundled Schema Registry + HTTP Proxy + Console

## Start

```bash
docker network create data-platform-network 2>/dev/null || true
docker compose up -d
```

UI: http://localhost:8090

## Endpoints

- **Kafka (in-network)**: `redpanda:9092`
- **Kafka (host)**: `localhost:9093`
- **Schema Registry (in-network)**: `redpanda:8081`
- **Schema Registry (host)**: `localhost:18081`
- **Console**: `localhost:8090`
- **Admin API**: `localhost:19644`

## Topic management

```bash
# List topics
docker exec redpanda rpk topic list

# Create a topic
docker exec redpanda rpk topic create spotify.player.current --partitions 3

# Tail messages
docker exec redpanda rpk topic consume spotify.player.current

# Tail schema-contract rejects (dead-letter topic)
docker exec redpanda rpk topic consume spotify.player.current.dlq
```

## Schema Registry

The bundled registry holds the JSON Schema contract for `spotify.player.current`
(subject `spotify.player.current-value`, source file `ingestion/spotify/schemas/`).
The producer registers it at startup and validates every event before producing;
rejects route to `spotify.player.current.dlq`. Browse schemas in the Console
(`localhost:8090`) or:

```bash
curl -s localhost:18081/subjects
curl -s localhost:18081/subjects/spotify.player.current-value/versions/latest
```

## Migration notes

- Switch producers / ClickHouse Kafka engine `kafka_broker_list` from `kafka:9092` → `redpanda:9092`. No other changes.
- Topic config (partitions, replication, retention) does not auto-migrate from the existing Kafka cluster. Recreate topics on Redpanda as needed.
- The current Kafka compose at `../kafka/` can keep running on the same network during evaluation; just make sure host port 9092 / 9093 / 8081 / 8090 don't collide (the current Kafka uses 9092/9093/8081/8090 — choose one stack at a time, or remap the published ports here).
