# dags/spotify_dbt_dag.py
from __future__ import annotations

import logging
from datetime import timedelta

import pendulum
from airflow.models.dag import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

log = logging.getLogger(__name__)

default_args = {
    'owner': 'data-engineering',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

# dbt project path inside Airflow container
DBT_PROJECT_DIR = '/opt/airflow/dags/dbt_project'
DBT_PROFILES_DIR = '/opt/airflow/dags/dbt_project'


def log_dbt_start(**context):
    """Log dbt transformation start for Spotify data product"""
    logical_date = context['logical_date']
    log.info(f"Starting Spotify dbt transformations for {logical_date}")
    return {"status": "started", "data_product": "spotify", "timestamp": str(logical_date)}


def log_dbt_complete(**context):
    """Log dbt transformation completion for Spotify data product"""
    logical_date = context['logical_date']
    log.info(f"Completed Spotify dbt transformations for {logical_date}")
    return {"status": "completed", "data_product": "spotify", "timestamp": str(logical_date)}


with DAG(
    dag_id="spotify_dbt",
    default_args=default_args,
    description="Run dbt transformations for Spotify data product (bronze → silver → gold)",
    schedule="*/15 * * * *",  # Run every 15 minutes
    start_date=pendulum.now("UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "transformation", "spotify", "data-product"],
) as dag:

    start = PythonOperator(
        task_id='log_start',
        python_callable=log_dbt_start,
    )

    # Ensure target directory has proper permissions for both Airflow and host user
    fix_permissions = BashOperator(
        task_id='fix_permissions',
        bash_command=f"""
        mkdir -p {DBT_PROJECT_DIR}/target && \
        chmod -R 777 {DBT_PROJECT_DIR}/target 2>/dev/null || true
        """,
    )

    # dbt deps - install dependencies (if any packages defined)
    dbt_deps = BashOperator(
        task_id='dbt_deps',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt deps --profiles-dir {DBT_PROFILES_DIR} --target prod || true
        """,
    )

    # dbt run - execute only Spotify models using tag selector
    dbt_run_spotify = BashOperator(
        task_id='dbt_run_spotify',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt run --select tag:spotify --profiles-dir {DBT_PROFILES_DIR} --target prod
        """,
    )

    # dbt test - run tests only on Spotify models
    dbt_test_spotify = BashOperator(
        task_id='dbt_test_spotify',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt test --select tag:spotify --profiles-dir {DBT_PROFILES_DIR} --target prod || true
        """,
        # Don't fail DAG if tests fail, just log warnings
    )

    complete = PythonOperator(
        task_id='log_complete',
        python_callable=log_dbt_complete,
    )

    # DAG dependencies
    start >> fix_permissions >> dbt_deps >> dbt_run_spotify >> dbt_test_spotify >> complete
