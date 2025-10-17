"""Utilities for emitting structured audit events."""

from __future__ import annotations

import logging
from typing import Any

from .config import get_settings
from .audit_queue import get_audit_queue

AUDIT_LOGGER_NAME = "app.audit"


def get_audit_logger() -> logging.Logger:
    """Return the configured audit logger."""

    return logging.getLogger(AUDIT_LOGGER_NAME)


def audit_event(event: str, **details: Any) -> None:
    """Emit an audit log entry if auditing is enabled."""

    settings = get_settings()
    if not settings.audit_log_enabled:
        return

    payload = {"event": event}
    if details:
        payload.update(details)

    logger = get_audit_logger()
    logger.info(event, extra=payload)

    queue = get_audit_queue()
    if queue:
        try:
            queue.enqueue(payload | {"event": event})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("audit_queue_enqueue_failed", extra={"error": str(exc)})
