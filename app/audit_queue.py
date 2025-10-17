"""Asynchronous audit queue helpers."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from queue import Full, Queue
from typing import Any, Protocol

from .config import get_settings

logger = logging.getLogger("app.audit_queue")

try:  # pragma: no cover - optional dependency
    from kafka import KafkaProducer  # type: ignore
except Exception:  # pragma: no cover - gracefully degrade
    KafkaProducer = None  # type: ignore


class AuditQueue(Protocol):  # pragma: no cover - interface only
    """Protocol representing queue backends."""

    def enqueue(self, payload: dict[str, Any]) -> None:
        ...


class MemoryAuditQueue:
    """In-memory queue retaining recent audit events for testing or dev."""

    def __init__(self, maxsize: int) -> None:
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=maxsize)

    def enqueue(self, payload: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except Full:
            logger.warning("audit_queue_memory_full", extra={"discarded_event": payload.get("event")})

    def drain(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while not self._queue.empty():
            items.append(self._queue.get_nowait())
        return items


class KafkaAuditQueue:
    """Kafka-backed queue pushing audit events to a topic."""

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        if KafkaProducer is None:
            raise RuntimeError("kafka-python is required for Kafka audit queue")
        self._topic = topic
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    def enqueue(self, payload: dict[str, Any]) -> None:
        future = self._producer.send(self._topic, payload)
        future.add_errback(self._on_error)

    def _on_error(self, exc: BaseException) -> None:
        logger.error("audit_queue_kafka_error", extra={"error": str(exc)})


@lru_cache()
def get_audit_queue() -> AuditQueue | None:
    """Return the configured audit queue backend or None when disabled."""

    settings = get_settings()
    if not settings.audit_queue_enabled:
        return None

    if settings.audit_queue_backend == "memory":
        return MemoryAuditQueue(settings.audit_queue_memory_maxsize)

    if settings.audit_queue_backend == "kafka":
        if not settings.audit_queue_kafka_bootstrap or not settings.audit_queue_kafka_topic:
            logger.error("audit_queue_kafka_missing_config")
            return None
        try:
            return KafkaAuditQueue(
                bootstrap_servers=settings.audit_queue_kafka_bootstrap,
                topic=settings.audit_queue_kafka_topic,
            )
        except Exception as exc:  # pragma: no cover - depends on kafka runtime
            logger.error("audit_queue_kafka_initialisation_failed", extra={"error": str(exc)})
            return None

    logger.error("audit_queue_unknown_backend", extra={"backend": settings.audit_queue_backend})
    return None


def reset_audit_queue_cache() -> None:
    """Reset cached queue instance (mainly for tests)."""

    get_audit_queue.cache_clear()
