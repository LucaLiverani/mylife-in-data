#!/usr/bin/env python3
"""CI gate for the spotify.player.current stream contract.

Three artifacts describe the same wire format and drift independently:

  1. the producer's _normalize_event() + json_utils.dumps() (what is emitted),
  2. the JSON Schema contract in ingestion/spotify/schemas/ (what is allowed),
  3. the ClickHouse Kafka-engine DDL (what the warehouse can ingest).

This script fails when any pair disagrees, which is exactly the failure mode
the contract exists for: before it, a renamed or retyped field sailed through
produce and was silently discarded by kafka_skip_broken_messages. Runs in CI
(backend-validate) with no broker, no warehouse, and no network.

Checks:
  A. the schema file is itself a valid draft-07 schema
  B. a realistic producer event (fixture → _normalize_event → dumps round
     trip) validates against the schema
  C. mutated events (renamed field, ISO-'T'/'Z' timestamp, retyped int,
     extra field, missing field) are all REJECTED — guards against the
     schema accidentally going vacuous
  D. schema properties == Kafka-engine DDL columns, with JSON-type ↔
     ClickHouse-type agreement
  E. DLQ envelope keys == DLQ Kafka-engine DDL columns
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jsonschema  # noqa: E402

from ingestion._shared.json_utils import dumps  # noqa: E402
from ingestion.spotify.producer_current import (  # noqa: E402
    _normalize_event,
    dlq_envelope,
    load_schema,
    serialize_event,
)

DDL_PATH = REPO_ROOT / "warehouse" / "ddl" / "10_spotify_current_track.sql"

# A realistic /me/player/currently-playing response (shape only — ids and
# names are arbitrary). Extend it if _normalize_event starts reading new keys.
API_FIXTURE = {
    "is_playing": True,
    "progress_ms": 73456,
    "item": {
        "id": "11dFghVXANMlKmJXsNCbNl",
        "name": "Cut To The Feeling",
        "uri": "spotify:track:11dFghVXANMlKmJXsNCbNl",
        "duration_ms": 207959,
        "album": {
            "id": "0tGPJ0bkWOUmH7MEOR77qc",
            "name": "Cut To The Feeling",
            "uri": "spotify:album:0tGPJ0bkWOUmH7MEOR77qc",
            "images": [
                {"url": "https://i.scdn.co/image/ab67616d0000b273aaaa", "height": 640, "width": 640},
                {"url": "https://i.scdn.co/image/ab67616d00001e02bbbb", "height": 300, "width": 300},
            ],
        },
        "artists": [{"id": "6sFIWsNpZYqfjUpaCgueju", "name": "Carly Rae Jepsen"}],
    },
    "device": {
        "id": "5fbb3ba6aa454b5534c4ba43a8c7e8e45a63ad0e",
        "name": "Web Player (Firefox)",
        "type": "Computer",
        "volume_percent": 64,
    },
    "context": {"type": "playlist", "uri": "spotify:playlist:37i9dQZF1DX0XUsuxWHRQd"},
}

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok  {label}")
    else:
        print(f"FAIL  {label}" + (f" — {detail}" if detail else ""))
        _FAILURES.append(label)


def wire_form(event: dict) -> dict:
    """The event exactly as the producer's value_serializer puts it on the wire."""
    return json.loads(dumps(event))


def ddl_columns(table: str) -> dict[str, str]:
    """{column: clickhouse_type} for one CREATE TABLE block in the DDL file."""
    sql = re.sub(r"--[^\n]*", "", DDL_PATH.read_text(encoding="utf-8"))
    m = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(table)}\s*\((.*?)\)\s*ENGINE",
        sql,
        flags=re.S,
    )
    if not m:
        raise SystemExit(f"could not find CREATE TABLE {table} in {DDL_PATH}")
    cols: dict[str, str] = {}
    for fragment in m.group(1).split(","):
        parts = fragment.split()
        if len(parts) >= 2:
            cols[parts[0]] = parts[1]
    return cols


def expected_json_type(ch_type: str) -> str:
    t = ch_type
    if t.startswith("LowCardinality(") and t.endswith(")"):
        t = t[len("LowCardinality("):-1]
    if t.startswith("DateTime"):
        return "string"
    if t == "String":
        return "string"
    if t in {"Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64"}:
        return "integer"
    if t == "Bool":
        return "boolean"
    if t.startswith("Array("):
        return "array"
    raise SystemExit(f"no JSON-type mapping for ClickHouse type {ch_type!r} — extend expected_json_type()")


def main() -> int:
    # ── A. schema file is valid ───────────────────────────────────────────
    schema = load_schema()  # Draft7Validator.check_schema inside
    validator = jsonschema.Draft7Validator(schema)
    check("schema file is a valid draft-07 schema", True)

    # ── B. the producer's own output passes ───────────────────────────────
    event = _normalize_event(API_FIXTURE)
    assert event is not None, "fixture unexpectedly normalized to None"
    good_errors = [e.message for e in validator.iter_errors(wire_form(event))]
    check(
        "producer fixture event validates",
        not good_errors,
        "; ".join(good_errors),
    )

    # ── C. broken events are rejected (schema is not vacuous) ─────────────
    def rejected(mutate) -> bool:
        bad = wire_form(_normalize_event(API_FIXTURE))
        mutate(bad)
        return any(validator.iter_errors(bad))

    def rename_track_id(e):
        e["trackId"] = e.pop("track_id")

    def iso_timestamp(e):
        e["captured_at"] = "2026-06-11T09:00:00.000Z"

    def retyped_int(e):
        e["track_duration_ms"] = str(e["track_duration_ms"])

    def extra_field(e):
        e["brand_new_field"] = 1

    def missing_field(e):
        del e["is_playing"]

    check("renamed field is rejected", rejected(rename_track_id))
    check("ISO-8601 'T'/'Z' timestamp is rejected", rejected(iso_timestamp))
    check("retyped integer is rejected", rejected(retyped_int))
    check("unknown extra field is rejected", rejected(extra_field))
    check("missing required field is rejected", rejected(missing_field))

    unserializable = dict(event)
    unserializable["album_images"] = {1, 2}  # a set: not JSON-serializable
    payload, errs = serialize_event(validator, unserializable)
    check(
        "non-serializable event degrades to a DLQ-able error, not an exception",
        bool(errs) and isinstance(payload, str),
        f"errors={errs!r}",
    )

    # ── D. schema ↔ Kafka-engine DDL parity ───────────────────────────────
    cols = ddl_columns("bronze.kafka_spotify_player_current")
    props = schema["properties"]
    check(
        "schema properties == kafka table columns",
        set(props) == set(cols),
        f"schema-only={sorted(set(props) - set(cols))} ddl-only={sorted(set(cols) - set(props))}",
    )
    check(
        "every schema property is required",
        set(schema.get("required", [])) == set(props),
        f"optional={sorted(set(props) - set(schema.get('required', [])))}",
    )
    for name in sorted(set(props) & set(cols)):
        want = expected_json_type(cols[name])
        got = props[name].get("type")
        check(f"type parity for {name} ({cols[name]} ↔ {got})", got == want)

    # ── E. DLQ envelope ↔ DLQ DDL parity ──────────────────────────────────
    envelope = wire_form(dlq_envelope(dumps(event), ["test error"]))
    dlq_cols = ddl_columns("bronze.kafka_spotify_player_current_dlq")
    check(
        "DLQ envelope keys == DLQ kafka table columns",
        set(envelope) == set(dlq_cols),
        f"envelope-only={sorted(set(envelope) - set(dlq_cols))} ddl-only={sorted(set(dlq_cols) - set(envelope))}",
    )

    if _FAILURES:
        print(f"\n{len(_FAILURES)} contract check(s) failed.")
        return 1
    print("\nStream contract OK: producer ↔ schema ↔ DDL agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
