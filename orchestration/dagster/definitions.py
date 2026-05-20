"""
Dagster entrypoint — placeholder definitions.

This is a scaffold so the Dagster container has something to load. The actual
asset/job port from the Airflow DAGs (in `../dags/`) is the next step of the
refactor. Each Airflow DAG below maps to a Dagster job/schedule:

    spotify_ingestion_dag.py      → Dagster job: spotify_recently_played
    spotify_artist_ingestion_dag  → Dagster job: spotify_artist_enrichment
    youtube_enrichment_dag        → Dagster job: youtube_enrichment
    google_export_initiator_dag   → Dagster job: google_takeout_initiate
    google_export_monitor_dag     → Dagster job: google_takeout_collect
    {spotify,youtube,maps,home}_dbt_dag → @dbt_assets via dagster-dbt

The dbt project lives at /opt/dagster/repo/transformations and integrates via
dagster-dbt's DbtCliResource.
"""

from dagster import Definitions, AssetExecutionContext, asset


@asset(group_name="meta")
def placeholder_health_check(context: AssetExecutionContext) -> str:
    """Sanity check asset — confirms the Dagster code location loaded successfully."""
    context.log.info("Dagster code location loaded.")
    return "ok"


defs = Definitions(
    assets=[placeholder_health_check],
)
