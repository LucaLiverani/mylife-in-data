# Airflow Setup

This directory contains the Docker Compose configuration for setting up an Apache Airflow instance.

The setup includes:
- PostgreSQL for the metadata database
- Redis for the Celery broker
- Airflow Webserver
- Airflow Scheduler
- Airflow Worker
- Airflow Triggerer

## Getting Started

### 1. Prerequisites

- Docker
- Docker Compose

### 2. Create `.env` file

Before starting, create a `.env` file in this directory. This file will hold your credentials and configuration. You can copy the example file:

```bash
cp .env.example .env
```

Update the `.env` file with your desired values. You will need to generate a Fernet key for `AIRFLOW__CORE__FERNET_KEY`:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Start the Services

You can start the Airflow instance using the main `start-all.sh` script in the parent directory, or by running the following command in this directory:

```bash
docker-compose up -d
```

## Accessing Airflow

- **Airflow Web UI**: `http://localhost:8080`

### Login Credentials

Airflow standalone mode auto-generates a password for the admin user. To get the password, run:

```bash
docker logs airflow-standalone 2>&1 | grep "Simple auth manager | Password"
```

- **Username**: admin
- **Password**: See output from the command above

## Update package for piepline

---

## When to Restart What:

| Change | Command |
|--------|---------|
| **DAG file edited** | Nothing! Wait 30s |
| **New package in requirements.txt** | `docker-compose build && docker-compose up -d` |
| **Config change** | `docker-compose restart airflow-scheduler` |
| **New Airflow connection** | Nothing if added via UI, or `docker-compose restart` |
| **Code in spotify/ module** | `docker-compose restart airflow-scheduler airflow-worker` |

---

## Quick Workflow:

```bash
# Daily work - edit DAGs
vim ~/projects/.../pipeline_code/spotify_ingestion_dag.py
# Auto-detected in 30s!

# Weekly/monthly - add package
echo "requests==2.31.0" >> ~/projects/.../pipeline_code/requirements.txt
cd ~/projects/.../infrastructure/airflow
docker-compose build && docker-compose up -d
# Takes ~2-3 minutes with caching
```
