FROM python:3.12-slim

WORKDIR /opt/dagster

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

# Dagster + adapters
RUN pip install --no-cache-dir \
      dagster \
      dagster-webserver \
      dagster-postgres \
      dagster-dbt \
      dagster-aws \
      dbt-core \
      dbt-clickhouse \
      clickhouse-connect \
      kafka-python \
      jsonschema \
      spotipy \
      google-auth google-auth-oauthlib google-api-python-client \
      pendulum python-dotenv requests boto3 prometheus-client

# Dagster instance config (where it stores runs/event logs)
ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p /opt/dagster/dagster_home

COPY infrastructure/compose/dagster/dagster.yaml /opt/dagster/dagster_home/dagster.yaml
COPY infrastructure/compose/dagster/workspace.yaml /opt/dagster/workspace.yaml

ENV PYTHONPATH=/opt/dagster/repo
WORKDIR /opt/dagster/repo
