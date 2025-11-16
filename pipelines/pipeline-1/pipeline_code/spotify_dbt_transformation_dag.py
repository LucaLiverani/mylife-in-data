# dags/spotify_dbt_transformation_dag.py
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
    """Log dbt transformation start"""
    logical_date = context['logical_date']
    log.info(f"Starting dbt transformations for {logical_date}")
    return {"status": "started", "timestamp": str(logical_date)}


def log_dbt_complete(**context):
    """Log dbt transformation completion"""
    logical_date = context['logical_date']
    log.info(f"Completed dbt transformations for {logical_date}")
    return {"status": "completed", "timestamp": str(logical_date)}


with DAG(
    dag_id="spotify_dbt_transformation",
    default_args=default_args,
    description="Run dbt transformations to create gold layer analytics tables",
    schedule="*/15 * * * *",  # Run every 15 minutes
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["spotify", "dbt", "transformation"],
) as dag:

    start = PythonOperator(
        task_id='log_start',
        python_callable=log_dbt_start,
    )

    # dbt deps - install dependencies (if any packages defined)
    dbt_deps = BashOperator(
        task_id='dbt_deps',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt deps --profiles-dir {DBT_PROFILES_DIR} --target prod || true
        """,
    )

    # dbt run - execute all models (silver + gold)
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt run --profiles-dir {DBT_PROFILES_DIR} --target prod
        """,
    )

    # dbt test - run tests on models
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt test --profiles-dir {DBT_PROFILES_DIR} --target prod || true
        """,
        # Don't fail DAG if tests fail, just log warnings
    )

    complete = PythonOperator(
        task_id='log_complete',
        python_callable=log_dbt_complete,
    )

    # DAG dependencies
    start >> dbt_deps >> dbt_run >> dbt_test >> complete
