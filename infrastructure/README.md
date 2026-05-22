# Infrastructure

Docker Compose stack for the data platform.

## Services

| Compose dir | Purpose | Host port(s) |
|---|---|---|
| `redpanda/` | Kafka-compatible broker + Console | 9093 (Kafka), 8090 (Console) |
| `clickhouse/` | OLAP warehouse + Keeper | 8123 (HTTP), 9200 (native), 9181 (Keeper) |
| `dagster/` | Webserver + daemon + Postgres metadata DB | 3000 (override with `DAGSTER_PORT` in `.env`) |
| `monitoring/` | Prometheus + Grafana | 9090 (Prom), 3001 (Grafana) |

All containers share the external network `data-platform-network`. Object storage uses Cloudflare R2 (configured via `.env`, not in compose).

## Configuration

Every service reads from a single `.env` file at `infrastructure/.env`. Each `compose/*/` directory has a `.env` symlink pointing at it, so:

- `cd infrastructure && ./start-all.sh` just works
- `cd compose/clickhouse && docker compose up -d` also works (the symlink resolves)

```bash
cp .env.example .env
chmod 600 .env
# edit .env — set CLICKHOUSE_PASSWORD, GRAFANA_ADMIN_PASSWORD, DAGSTER_POSTGRES_PASSWORD, R2 creds
```

No credentials are committed. Everything personal — including the username — flows through env vars.

## Bring up / down

```bash
./start-all.sh   # boots Redpanda → ClickHouse → Dagster → monitoring (idempotent)
./stop-all.sh    # stops everything
```

## R2 (object storage)

Cloudflare R2 is the object-storage layer, sitting outside the compose stack. Run once per environment to provision the bucket + write credentials into `.env`:

```bash
./provisioning/setup-r2.sh           # default bucket name: mylife-data-lake
# or
./provisioning/setup-r2.sh my-bucket
```

The script uses wrangler to create the bucket, prints the dashboard URL to mint a bucket-scoped API token, then writes `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` into `infrastructure/.env`.

## Provisioning a new VM

See `provisioning/README.md` for the bootstrap workflow (Docker install, GitHub deploy key, Cloudflare Tunnel install).
