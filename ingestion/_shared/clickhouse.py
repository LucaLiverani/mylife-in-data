"""ClickHouse client helpers — used by both producers and Dagster assets."""

from __future__ import annotations

import os
import time
from typing import Any, Iterable, Sequence

import clickhouse_connect
from clickhouse_connect.driver.client import Client


def get_client(database: str | None = None) -> Client:
    """Build a clickhouse-connect Client from env. Uses HTTP interface (8123)."""

    host = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
    user = os.environ.get("CLICKHOUSE_USER", "default")
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    db = database or os.environ.get("CLICKHOUSE_DATABASE", "default")

    # CLICKHOUSE_PORT in the env is the native 9000; the HTTP port is fixed at 8123
    # inside the compose network. Override with CLICKHOUSE_HTTP_PORT when needed.
    port = int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123"))

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        database=db,
        compress=False,
    )


def execute(sql: str, *, database: str | None = None, retries: int = 3) -> None:
    """Run a fire-and-forget statement, retrying transient failures."""

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            client = get_client(database=database)
            client.command(sql)
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def insert_rows(
    table: str,
    rows: Sequence[dict[str, Any]] | Iterable[dict[str, Any]],
    *,
    database: str | None = None,
    column_names: list[str] | None = None,
) -> None:
    """Insert rows into `<database>.<table>`. Rows may be dicts or already-aligned tuples."""

    rows = list(rows)
    if not rows:
        return

    client = get_client(database=database)

    if isinstance(rows[0], dict):
        if column_names is None:
            column_names = list(rows[0].keys())
        data = [[row.get(col) for col in column_names] for row in rows]
        client.insert(table, data, column_names=column_names)
    else:
        if column_names is None:
            raise ValueError("column_names required when rows are not dicts")
        client.insert(table, list(rows), column_names=column_names)


def execute_file(path: str, *, database: str | None = None) -> None:
    """Apply a `.sql` file, splitting on `;` after stripping comments.

    Mirrors warehouse/ddl/apply.sh: comments must be stripped BEFORE splitting
    on `;`, otherwise a `;` inside a line comment ("…dedup keys; Kafka would
    be overkill.") splits the comment in two and the right-hand fragment
    gets sent to ClickHouse as a bare statement → SYNTAX_ERROR.
    """
    import re

    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()

    # Strip --line and /* block */ comments before splitting on `;`.
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        execute(stmt, database=database)
