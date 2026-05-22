"""Dagster code location — clean starting point.

The previous Airflow DAGs in `../dags/` (now `_legacy/`) are kept as reference
only. Pipelines are being rewritten from scratch here.

What to keep from the legacy code:
    - `ingestion/spotify/authenticate_local.py` and the OAuth flow it sets up.
      The CacheFileHandler pattern from `ingestion/spotify/spotify_api.py`
      (`get_spotify_producer_client`) translates cleanly to a Dagster
      ConfigurableResource pointing at a file in DAGSTER_HOME.

What gets replaced:
    - All Airflow Variable usage (Fernet-encrypted, key now lost).
    - All Airflow-specific operators / connections.
    - The dbt-via-BashOperator pattern → `@dbt_assets` from `dagster-dbt`.

Until real assets land, this file just exposes a sanity-check asset so the
webserver has something to load.
"""

from dagster import Definitions, AssetExecutionContext, asset


@asset(group_name="meta")
def placeholder_health_check(context: AssetExecutionContext) -> str:
    """Confirms the Dagster code location loaded successfully."""
    context.log.info("Dagster code location loaded.")
    return "ok"


defs = Definitions(
    assets=[placeholder_health_check],
)
