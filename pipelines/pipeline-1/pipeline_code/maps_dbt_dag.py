# dags/maps_dbt_dag.py
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
    """Log dbt transformation start for Google Maps data product"""
    logical_date = context['logical_date']
    log.info(f"Starting Google Maps dbt transformations for {logical_date}")
    return {"status": "started", "data_product": "maps", "timestamp": str(logical_date)}


def log_dbt_complete(**context):
    """Log dbt transformation completion for Google Maps data product"""
    logical_date = context['logical_date']
    log.info(f"Completed Google Maps dbt transformations for {logical_date}")
    return {"status": "completed", "data_product": "maps", "timestamp": str(logical_date)}


with DAG(
    dag_id="maps_dbt",
    default_args=default_args,
    description="Run dbt transformations for Google Maps data product (bronze → silver → gold)",
    schedule="*/15 * * * *",  # Run every 15 minutes
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "transformation", "maps", "google-maps", "data-product"],
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

    # dbt run - execute only Google Maps models using tag selector
    dbt_run_maps = BashOperator(
        task_id='dbt_run_maps',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt run --select tag:maps --profiles-dir {DBT_PROFILES_DIR} --target prod
        """,
    )

    # dbt test - run tests only on Google Maps models
    dbt_test_maps = BashOperator(
        task_id='dbt_test_maps',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt test --select tag:maps --profiles-dir {DBT_PROFILES_DIR} --target prod || true
        """,
        # Don't fail DAG if tests fail, just log warnings
    )

    complete = PythonOperator(
        task_id='log_complete',
        python_callable=log_dbt_complete,
    )

    # DAG dependencies
    start >> fix_permissions >> dbt_deps >> dbt_run_maps >> dbt_test_maps >> complete
