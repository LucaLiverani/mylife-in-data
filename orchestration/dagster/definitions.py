"""Dagster code location — entrypoint loaded by workspace.yaml.

Resources are constructed once and injected into every asset that declares
`required_resource_keys` or has a typed `resource_*` parameter.

Assets are auto-discovered by importing every module under
`orchestration.dagster.assets.*`. New phases add a module there; no edits to
this file required (beyond the import).
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from typing import Any

from dagster import (
    Definitions,
    AssetsDefinition,
    ScheduleDefinition,
    SensorDefinition,
    asset,
    load_assets_from_modules,
)

from dagster_dbt import DbtCliResource

from orchestration.dagster import assets as assets_pkg
from orchestration.dagster.resources import (
    ClickHouseResource,
    R2Resource,
    RedpandaResource,
    GoogleAuthResource,
    SpotifyResource,
)


# ── Auto-discover every asset module ──────────────────────────────────────
def _discover_modules():
    modules = []
    for module_info in pkgutil.iter_modules(assets_pkg.__path__):
        modules.append(importlib.import_module(f"{assets_pkg.__name__}.{module_info.name}"))
    return modules


_asset_modules = _discover_modules()
_discovered_assets = load_assets_from_modules(_asset_modules) if _asset_modules else []


# Collect any schedules / sensors a module exposes at module-level.
# Gated on DAGSTER_SCHEDULES_ENABLED: laptop (dev) leaves it unset so schedules
# and sensors don't auto-tick locally and race the VM's runs. Assets always
# load; you can still manually materialize them from the UI on the laptop.
_SCHEDULES_ON = os.environ.get("DAGSTER_SCHEDULES_ENABLED") == "1"


def _collect(name: str) -> list[Any]:
    if not _SCHEDULES_ON:
        return []
    out: list[Any] = []
    for m in _asset_modules:
        for sym in dir(m):
            obj = getattr(m, sym)
            if isinstance(obj, ScheduleDefinition) and name == "schedules":
                out.append(obj)
            elif isinstance(obj, SensorDefinition) and name == "sensors":
                out.append(obj)
    return out


@asset(group_name="meta")
def placeholder_health_check(context) -> str:
    """Confirms the Dagster code location loaded successfully."""
    context.log.info("Dagster code location loaded.")
    return "ok"


_all_assets: list[Any] = [placeholder_health_check, *list(_discovered_assets)]


defs = Definitions(
    assets=_all_assets,
    schedules=_collect("schedules"),
    sensors=_collect("sensors"),
    resources={
        "clickhouse": ClickHouseResource(),
        "redpanda": RedpandaResource(),
        "r2": R2Resource(),
        "spotify": SpotifyResource(),
        # Google enforces that Data Portability scopes can't share an OAuth
        # flow with anything else, so we keep two separate credential rows.
        "google_auth_standard": GoogleAuthResource(scope_group="standard"),
        "google_auth_portability": GoogleAuthResource(scope_group="portability"),
        # dbt project lives at /opt/dagster/transformations in the container
        # (bind-mounted from the host). profiles.yml is auto-created from
        # profiles.yml.example by orchestration/dagster/assets/dbt.py on
        # code-location load. Target pinned to `prod`: the `dev` output writes
        # to dev_silver/dev_gold (generate_schema_name prefixes non-prod
        # targets) and must never be what the scheduled build runs.
        "dbt": DbtCliResource(
            project_dir="/opt/dagster/transformations",
            profiles_dir="/opt/dagster/transformations",
            target="prod",
        ),
    },
)
