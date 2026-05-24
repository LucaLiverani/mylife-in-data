"""JSON encode/decode with datetime coercion. ClickHouse Kafka engine reads
JSONEachRow — datetimes serialize as ISO-8601 strings, ms epoch decodes back."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default, separators=(",", ":"))


def loads(s: str | bytes) -> Any:
    return json.loads(s)


def from_ms(ms: int | float | None) -> datetime | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
