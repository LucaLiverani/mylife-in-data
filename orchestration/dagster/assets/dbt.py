"""dbt models — silver + gold transformations layered on bronze.

Exposes every dbt model in `transformations/` as a Dagster asset via
`dagster-dbt`. The lineage view shows the full bronze → silver → gold DAG;
the dashboard's `gold.*` queries get real data once these run.

Self-bootstrap behaviour on import:
  1. If `transformations/profiles.yml` is missing, copy it from
     `profiles.yml.example` (all values are env_var() interpolated — no
     secrets in the example, so it's safe to use verbatim).
  2. If `transformations/target/manifest.json` is missing OR older than any
     of the dbt source files (models, dbt_project.yml, sources/schema yml,
     macros), run `dbt parse` to regenerate it.

That way a fresh VM picks up dbt automatically on first Dagster boot; no
manual `dbt parse` step required in deploy.sh.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    ScheduleDefinition,
    define_asset_job,
)
from dagster_dbt import DbtCliResource, dbt_assets


# In the Dagster container, transformations/ is bind-mounted RW at this path.
DBT_PROJECT_DIR = Path("/opt/dagster/transformations")
PROFILES_YML = DBT_PROJECT_DIR / "profiles.yml"
PROFILES_EXAMPLE = DBT_PROJECT_DIR / "profiles.yml.example"
MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"


def _ensure_profiles_yml() -> None:
    """Copy profiles.yml.example → profiles.yml if missing."""
    if PROFILES_YML.exists():
        return
    if not PROFILES_EXAMPLE.exists():
        raise RuntimeError(
            f"Neither {PROFILES_YML} nor {PROFILES_EXAMPLE} exists — dbt cannot run."
        )
    shutil.copy(PROFILES_EXAMPLE, PROFILES_YML)


def _manifest_stale() -> bool:
    """True if manifest is missing or older than any dbt source file."""
    if not MANIFEST_PATH.exists():
        return True
    manifest_mtime = MANIFEST_PATH.stat().st_mtime
    sources: list[Path] = [DBT_PROJECT_DIR / "dbt_project.yml"]
    for pattern in ("models/**/*.sql", "models/**/*.yml", "macros/**/*.sql"):
        sources.extend(DBT_PROJECT_DIR.glob(pattern))
    return any(p.stat().st_mtime > manifest_mtime for p in sources if p.exists())


def _ensure_manifest() -> None:
    """Run `dbt parse` if manifest is missing/stale. Idempotent + cheap."""
    if not _manifest_stale():
        return
    subprocess.run(
        [
            "dbt",
            "parse",
            "--project-dir", str(DBT_PROJECT_DIR),
            "--profiles-dir", str(DBT_PROJECT_DIR),
        ],
        check=True,
        env={**os.environ},
    )


# Run bootstrap at module import time (Dagster code-location load).
# Wrapped in try/except so a failure here (missing project dir, dbt parse
# errors, etc.) doesn't take out the whole Dagster code location — the
# other ingest assets keep loading. Errors surface in container logs.
if DBT_PROJECT_DIR.exists():
    try:
        _ensure_profiles_yml()
        _ensure_manifest()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "dbt bootstrap failed (skipping dbt assets): %s", exc
        )


# Only define the asset if the manifest is actually on disk. Without this
# guard, @dbt_assets(manifest=...) raises at import time when the file is
# missing, breaking every other asset registration.
if MANIFEST_PATH.exists():
    @dbt_assets(manifest=MANIFEST_PATH)
    def mylife_dbt_assets(context, dbt: DbtCliResource):
        """Run `dbt build` over every model — compiles, runs, then tests each one.

        Materializing this asset from the Dagster UI runs the full silver +
        gold DAG. Individual model selection via the UI's asset-selection
        filter is supported by dagster-dbt automatically.

        Note: `context` is intentionally unannotated — Dagster's validator
        rejects an explicit AssetExecutionContext hint here due to a class-
        identity mismatch between dagster and dagster-dbt's resolution path.
        """
        yield from dbt.cli(["build"], context=context).stream()


    # Daily rebuild at 09:00 UTC. By this time all bronze ingest schedules
    # have run (Maps 04:00, YouTube 04:30, Calendar renew 06:00, freshness
    # monitor 08:00), so silver + gold pick up the latest bronze data.
    dbt_build_job = define_asset_job(
        "dbt_build_job",
        selection=AssetSelection.assets(mylife_dbt_assets),
    )


    dbt_build_schedule = ScheduleDefinition(
        job=dbt_build_job,
        cron_schedule="0 9 * * *",
        name="dbt_build_schedule",
        description="Daily 09:00 UTC — rebuild all silver + gold dbt models.",
        default_status=DefaultScheduleStatus.RUNNING,
    )
