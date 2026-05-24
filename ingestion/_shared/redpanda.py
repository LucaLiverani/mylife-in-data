"""Redpanda/Kafka producer factory."""

from __future__ import annotations

import json
import os
from typing import Any

from kafka import KafkaProducer

from .json_utils import dumps


def get_producer(**overrides: Any) -> KafkaProducer:
    """Return a JSON-encoding KafkaProducer wired to the Redpanda broker."""

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    config = dict(
        bootstrap_servers=bootstrap.split(","),
        value_serializer=lambda v: dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
        acks="all",
        linger_ms=10,
        retries=3,
    )
    config.update(overrides)
    return KafkaProducer(**config)
