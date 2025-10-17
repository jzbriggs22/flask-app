"""Configure JSON logging for the service."""

from __future__ import annotations

import logging
from logging import Handler
from logging.handlers import HTTPHandler
from urllib.parse import urlparse

from pythonjsonlogger import jsonlogger

from .audit import AUDIT_LOGGER_NAME
from .config import get_settings


def _json_formatter() -> jsonlogger.JsonFormatter:
    return jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")


def _build_audit_handler(settings) -> Handler:
    destination = settings.audit_log_destination
    if destination == "file" and settings.audit_log_file_path:
        handler = logging.FileHandler(settings.audit_log_file_path)
        handler.setFormatter(_json_formatter())
        return handler

    if destination == "http" and settings.audit_log_http_endpoint:
        parsed = urlparse(settings.audit_log_http_endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logging.getLogger(__name__).warning(
                "audit_http_endpoint_invalid", extra={"endpoint": settings.audit_log_http_endpoint}
            )
        else:
            handler = HTTPHandler(
                host=parsed.netloc,
                url=f"{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}",
                method="POST",
            )
            handler.setFormatter(_json_formatter())
            return handler

    handler = logging.StreamHandler()
    handler.setFormatter(_json_formatter())
    return handler


def configure_logging() -> None:
    """Set up JSON logging compatible with SIEM ingestion."""

    settings = get_settings()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(_json_formatter())
    root_logger.handlers = [handler]

    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    audit_logger.handlers = [_build_audit_handler(settings)]
