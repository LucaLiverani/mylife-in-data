# My Life in Data

Personal data platform: collect data from Spotify, YouTube, and Google Takeout; warehouse it in ClickHouse; transform it with dbt; visualize on a Cloudflare-hosted dashboard.

## Layout

```
ingestion/            Source-specific code (one folder per data source)
  spotify/            Spotify API client, OAuth, real-time Kafka producer
  youtube/            YouTube Data API enrichment of watch history
  google_takeout/     Google Data Portability API export client

orchestration/        Airflow — DAGs, requirements, plugins
  dags/               One file per DAG

warehouse/            ClickHouse — DDL, Kafka tables, S3Queue setup, materialized views
  ddl/                SQL files (run with clickhouse-client)

transformations/      dbt project (bronze/silver/gold by domain)
  models/{bronze,silver,gold}/{spotify,youtube,maps,home}/

dashboard/            React + Vite + Cloudflare Workers Functions (Pages-deployed)

infrastructure/       Deployment — Docker Compose, start/stop scripts
  compose/{airflow,kafka,clickhouse,storage,monitoring}/
  start-all.sh        Bring everything up
  stop-all.sh         Tear everything down

exploration/          Jupyter notebooks + DuckDB sandbox (not part of the prod path)

docs/                 Architecture diagrams, deployment guide, decision records
```

## Data flow

```
Spotify API ──┬─ producer ────────► Kafka ──► ClickHouse (Kafka engine + MVs) ──┐
              └─ Airflow DAG (batch) ─► MinIO/R2 ──► ClickHouse (S3Queue) ──────┤
                                                                                ├──► dbt (bronze→silver→gold) ──► Cloudflare dashboard
YouTube API ─── Airflow DAG (daily) ─► MinIO/R2 ──► ClickHouse (S3Queue) ──────┤
                                                                                │
Google Takeout ─ Airflow DAG (daily) ─► MinIO/R2 ──► ClickHouse (S3Queue) ─────┘
```

## Quick start (local)

```bash
cp .env.example .env  # fill in credentials
cd infrastructure && ./start-all.sh
```

Then visit:
- Airflow UI: http://localhost:8080
- MinIO Console: http://localhost:9001
- Kafka UI: http://localhost:8090
- ClickHouse HTTP: http://localhost:8123
- Grafana: http://localhost:3001

Per-component READMEs:
- `ingestion/spotify/README.md` — Spotify OAuth setup and DAG description
- `ingestion/google_takeout/README.md` — Google Data Portability OAuth
- `warehouse/ddl/README.md` — ClickHouse table/MV setup
- `transformations/README.md` — dbt model layout
- `dashboard/README.md` — Cloudflare Pages deployment
- `infrastructure/compose/airflow/README.md` — Airflow operational notes
- `docs/architecture.md` — overall architecture diagram
- `docs/deployment.md` — end-to-end deployment walkthrough
