# My Life in Data

Personal data platform: collect signals from streaming services (Spotify, YouTube, Google Maps), warehouse them in ClickHouse, and visualize on a Cloudflare-hosted dashboard.

The pipelines are being rewritten from scratch on this stack. The legacy Airflow + Kafka + MinIO incarnation has been removed; ingestion code currently exists only for the OAuth handshake (`ingestion/spotify/authenticate_local.py`).

## Layout

```
ingestion/spotify/      OAuth flow (the only piece kept from the legacy code)
orchestration/dagster/  Dagster code location (placeholder — pipelines TBD)
infrastructure/         Docker Compose stack + provisioning scripts
dashboard/              React + Vite + Cloudflare Pages Functions
exploration/            Jupyter sandbox (not part of the prod path)
DEPLOYMENT_PLAN.md      Step-by-step plan: local → VM → tunnel → dashboard rewire
```

## Stack

| Service | Purpose | Port |
|---|---|---|
| Redpanda | Kafka-compatible event streaming | 9093 (host) / 9092 (network) |
| ClickHouse | Columnar OLAP warehouse | 8123 (HTTP) / 9200 (native) |
| Dagster | Asset-based orchestration | 3030 |
| Prometheus + Grafana | Monitoring | 9090 / 3001 |

Object storage: Cloudflare R2 (provisioned outside the compose stack). Every credential — ClickHouse, Grafana, Dagster Postgres — flows from `infrastructure/.env` (gitignored), referenced via `${VAR}` in compose YAML. Nothing personal is hardcoded in any committed file.

## Quick start (local)

```bash
cd infrastructure
cp .env.example .env       # then chmod 600 .env and fill in real values
./start-all.sh
```

URLs printed at the end. The stack uses one identity across every service — username + password come from `infrastructure/.env`.

```bash
./stop-all.sh
```

## Production deploy

See `DEPLOYMENT_PLAN.md` — five phases ending with the Cloudflare Pages dashboard reading live ClickHouse via a Cloudflare Tunnel.
