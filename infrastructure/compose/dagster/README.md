# Dagster

Lighter, asset-based replacement for Airflow.

## Why

- Asset-based model maps 1:1 to bronze/silver/gold dbt layers
- Native dbt integration via `dagster-dbt` (auto-generates assets from your dbt project)
- ~1 GB RAM total (webserver + daemon + Postgres) vs ~3.5 GB for Airflow + Celery + Redis
- One Python process per role; no Celery broker, no triggerer, no statsd

## Status: SCAFFOLD

This compose stands up a Dagster instance with a placeholder code location at
`orchestration/dagster/definitions.py`. Porting the existing Airflow DAGs to
Dagster jobs / assets is the next step of the refactor — see the comment block
in `definitions.py` for the mapping.

## Start

```bash
docker network create data-platform-network 2>/dev/null || true
docker compose up -d --build
```

Webserver UI: http://localhost:3000

## Layout

```
infrastructure/compose/dagster/
  docker-compose.yml     # webserver + daemon + Postgres
  Dockerfile             # python:3.12-slim + dagster + dagster-dbt + adapters
  dagster.yaml           # instance config (storage, run coordinator)
  workspace.yaml         # points to orchestration/dagster/definitions.py

orchestration/dagster/
  definitions.py         # Dagster code location — placeholder for now
```

## Once Airflow is fully replaced

- Delete `infrastructure/compose/airflow/`
- Delete `orchestration/dags/` (Airflow DAG files)
- Delete `orchestration/.airflowignore`
- Move Airflow-specific Python deps out of `orchestration/requirements.txt`
