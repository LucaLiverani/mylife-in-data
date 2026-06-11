"""Redpanda/Kafka producer factory + topic admin helpers."""

from __future__ import annotations

import json
import os
from typing import Any

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from .json_utils import dumps


def _bootstrap_servers() -> list[str]:
    return os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092").split(",")


def get_producer(**overrides: Any) -> KafkaProducer:
    """Return a JSON-encoding KafkaProducer wired to the Redpanda broker."""

    config = dict(
        bootstrap_servers=_bootstrap_servers(),
        value_serializer=lambda v: dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
        acks="all",
        linger_ms=10,
        retries=3,
    )
    config.update(overrides)
    return KafkaProducer(**config)


def ensure_topic(
    name: str,
    *,
    num_partitions: int = 1,
    replication_factor: int = 1,
    retention_ms: int | None = None,
) -> None:
    """Create `name` if it does not exist; existing topics are left untouched.

    start-all.sh creates the topics on a full boot; this covers deploys, where
    only containers are recreated (the producer calls it at startup for its
    DLQ topic)."""

    configs = {"retention.ms": str(retention_ms)} if retention_ms else {}
    admin = KafkaAdminClient(bootstrap_servers=_bootstrap_servers())
    try:
        admin.create_topics(
            [
                NewTopic(
                    name=name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                    topic_configs=configs,
                )
            ]
        )
    except TopicAlreadyExistsError:
        pass
    finally:
        admin.close()
