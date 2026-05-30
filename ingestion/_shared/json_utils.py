"""JSON encode/decode with datetime coercion. Datetimes are emitted in the
"YYYY-MM-DD HH:MM:SS.mmm" (UTC) form that ClickHouse's Kafka-engine JSONEachRow
reader parses with its default date_time_input_format='basic'.

NOTE: the previous ISO-8601 'T'/'Z' form was rejected by that parser, so every
Kafka message (e.g. spotify.player.current) was silently dropped via
kafka_skip_broken_messages — the now-playing table never populated."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        dt = obj.astimezone(timezone.utc)
        # Space separator, millisecond precision, no 'Z' — ClickHouse-basic-friendly.
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default, separators=(",", ":"))


def loads(s: str | bytes) -> Any:
    return json.loads(s)


def from_ms(ms: int | float | None) -> datetime | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
