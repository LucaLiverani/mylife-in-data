"""Dagster code location — entrypoint loaded by workspace.yaml.

Resources are constructed once and injected into every asset that declares
`required_resource_keys` or has a typed `resource_*` parameter.

Assets are auto-discovered by importing every module under
`orchestration.dagster.assets.*`. New phases add a module there; no edits to
this file required (beyond the import).
"""

from __future__ import annotations

import importlib
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
def _collect(name: str) -> list[Any]:
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
        "google_auth": GoogleAuthResource(),
    },
)
