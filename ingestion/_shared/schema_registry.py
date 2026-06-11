"""Minimal Confluent-compatible Schema Registry client (Redpanda bundles one
at :8081).

Used by the now-playing producer to publish the topic's JSON Schema contract
so it is externally visible, versioned, and compatibility-checked. Enforcement
happens producer-side (jsonschema validation before produce): the ClickHouse
Kafka engine reads plain JSONEachRow, so the Confluent wire format (magic byte
+ schema id prefix) cannot be used on this topic, and broker-side schema-id
validation is off the table. The registry is the contract store, not the
enforcement point — which is why every call here is best-effort and the
producer keeps running on the local schema file when the registry misbehaves.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_REGISTRY_URL = "http://redpanda:8081"


def registry_url() -> str:
    return os.environ.get("SCHEMA_REGISTRY_URL", DEFAULT_REGISTRY_URL).rstrip("/")


def ensure_registered(
    subject: str,
    schema: dict[str, Any],
    *,
    compatibility: str = "BACKWARD",
    url: str | None = None,
    timeout: float = 10.0,
) -> int | None:
    """Register `schema` under `subject`; returns its schema id, or None.

    Idempotent: re-posting a schema identical to a registered version returns
    the existing id without creating a new version. Failure modes by design:

    - Registry unreachable → WARNING, return None. The local schema file is
      the same artifact registration would push, so validation is unaffected.
    - HTTP 409 (incompatible with the registered latest under the subject's
      compatibility mode) → ERROR, return None. Producing continues against
      the LOCAL schema so the stream stays alive; the conflict needs a human
      (evolve the schema compatibly, or relax /config/<subject>). Runbook:
      docs/OPERATIONS.md.
    """
    base = url or registry_url()
    headers = {"Content-Type": "application/vnd.schemaregistry.v1+json"}
    try:
        resp = requests.post(
            f"{base}/subjects/{subject}/versions",
            json={"schema": json.dumps(schema), "schemaType": "JSON"},
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code == 409:
            log.error(
                "Schema for subject %s is INCOMPATIBLE with the registered "
                "version (HTTP 409: %s). Producing continues against the "
                "local schema file — evolve the schema compatibly or relax "
                "the subject's compatibility, then restart the producer.",
                subject,
                resp.text.strip(),
            )
            return None
        resp.raise_for_status()
        schema_id = resp.json().get("id")
        log.info("Schema registered for subject %s (id=%s)", subject, schema_id)

        # Pin the subject's compatibility mode so future evolutions are
        # checked. Best-effort: a failure here loses the compat gate, not data.
        try:
            requests.put(
                f"{base}/config/{subject}",
                json={"compatibility": compatibility},
                headers=headers,
                timeout=timeout,
            ).raise_for_status()
        except requests.RequestException as exc:
            log.warning(
                "Could not set %s compatibility on subject %s: %s",
                compatibility, subject, exc,
            )
        return schema_id
    except requests.RequestException as exc:
        log.warning(
            "Schema Registry unreachable at %s (%s) — continuing with "
            "local-file validation only.",
            base, exc,
        )
        return None
