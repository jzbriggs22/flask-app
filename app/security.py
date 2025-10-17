"""Security utilities such as rate limiting, authentication, and metrics auth."""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import audit_event
from .config import get_settings
from .database import get_session, get_session_factory
from .models import ApiKey, ApiKeyArchive
from .rate_limiter import RateLimiter, get_rate_limiter

logger = logging.getLogger("app.security")


def _record_error(record: ApiKey, reason: str, session: Session) -> None:
    """Persist error analytics for a key."""

    record.error_count += 1
    record.last_error_at = datetime.utcnow()
    record.last_error_reason = reason
    if reason == "expired":
        record.is_active = False
    session.add(record)
    session.commit()


def _archive_key(session: Session, record: ApiKey, reason: str) -> ApiKeyArchive:
    archive = ApiKeyArchive(
        api_key_id=record.id,
        name=record.name,
        owner_email=record.owner_email,
        description=record.description,
        scopes=record.scopes or [],
        expires_at=record.expires_at,
        archive_reason=reason,
        last_error_reason=record.last_error_reason,
        request_count=record.request_count,
        error_count=record.error_count,
    )
    session.add(archive)
    session.delete(record)
    return archive


class RateLimitDependency:
    """Reusable dependency enforcing per-route limits."""

    def __init__(self) -> None:
        settings = get_settings()
        self._limiter: RateLimiter | None = None
        if settings.rate_limit_enabled:
            try:
                self._limiter = get_rate_limiter(
                    backend=settings.rate_limit_backend,
                    limit=settings.rate_limit_per_minute,
                    window_seconds=60.0,
                    burst=settings.rate_limit_burst,
                    redis_url=settings.rate_limit_redis_url,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "rate_limiter_initialisation_failed",
                    extra={"backend": settings.rate_limit_backend, "error": str(exc)},
                )
                self._limiter = None
        self._header = settings.rate_limit_identifier_header or settings.api_key_header

    def __call__(self, request: Request) -> None:
        if not self._limiter:
            return

        principal = getattr(request.state, "principal", None)
        if principal:
            identifier = principal
        else:
            api_key = request.headers.get(self._header)
            client_host = request.client.host if request.client else "anonymous"
            identifier = api_key or client_host
        key = f"{identifier}:{request.url.path}"

        if not self._limiter.allow(key):
            logger.warning(
                "rate_limit_exceeded",
                extra={"identifier": identifier, "path": request.url.path},
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Reduce request frequency.",
            )

    def reset(self) -> None:
        if self._limiter:
            self._limiter.reset()


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256 for persistent comparison."""

    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKeyAuthDependency:
    """Validate inbound requests using stored API keys."""

    def __init__(self, require: bool = True) -> None:
        settings = get_settings()
        self._enabled = settings.api_auth_enabled
        self._header = settings.api_key_header
        self._hmac_enabled = settings.api_hmac_enabled
        self._signature_header = settings.api_signature_header
        self._timestamp_header = settings.api_timestamp_header
        self._tolerance = settings.api_timestamp_tolerance_seconds
        self._default_ttl_days = settings.api_key_default_ttl_days
        self._require = require

    async def __call__(
        self,
        request: Request,
        session: Session = Depends(get_session),
    ) -> None:
        if not self._enabled:
            return

        provided = request.headers.get(self._header)
        if not provided:
            if not self._require:
                return
            logger.warning(
                "api_key_missing",
                extra={"path": request.url.path, "client": request.client.host if request.client else None},
            )
            audit_event(
                "api_key_missing",
                path=request.url.path,
                client=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key.",
            )

        if self._hmac_enabled:
            self._validate_hmac(request, provided)

        key_hash = hash_api_key(provided)
        record = session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        ).scalar_one_or_none()

        if not record:
            logger.warning(
                "api_key_invalid",
                extra={"path": request.url.path, "client": request.client.host if request.client else None},
            )
            audit_event(
                "api_key_invalid",
                path=request.url.path,
                client=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive API key.",
            )

        record.request_count += 1

        if record.is_expired:
            _record_error(record, "expired", session)
            logger.warning(
                "api_key_expired",
                extra={"api_key_id": record.id, "owner": record.owner_email},
            )
            audit_event(
                "api_key_expired",
                api_key_id=record.id,
                api_key_name=record.name,
                owner_email=record.owner_email,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired.",
            )

        required_scope = self._resolve_scope(request)
        if required_scope and not record.scope_allows((required_scope, "all")):
            logger.warning(
                "api_key_scope_block",
                extra={
                    "api_key_id": record.id,
                    "required_scope": required_scope,
                    "scopes": record.scopes,
                },
            )
            _record_error(record, f"missing_scope:{required_scope}", session)
            audit_event(
                "api_key_scope_block",
                api_key_id=record.id,
                api_key_name=record.name,
                required_scope=required_scope,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key lacks required scope.",
            )

        record.last_used_at = datetime.utcnow()
        if self._default_ttl_days and not record.expires_at:
            record.expires_at = datetime.utcnow() + timedelta(days=self._default_ttl_days)
        session.add(record)
        session.commit()

        request.state.principal = f"api-key:{record.id}"
        request.state.api_key_scopes = set(record.scopes or [])
        request.state.api_key_owner = record.owner_email

        logger.info(
            "api_key_authenticated",
            extra={
                "api_key_id": record.id,
                "owner": record.owner_email,
                "scopes": record.scopes,
                "path": request.url.path,
            },
        )

    def _validate_hmac(self, request: Request, provided_key: str) -> None:
        timestamp_value = request.headers.get(self._timestamp_header)
        signature = request.headers.get(self._signature_header)
        if not timestamp_value or not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing timestamp or signature headers.",
            )

        try:
            request_time = float(timestamp_value)
        except ValueError as exc:  # pragma: no cover - defensive
            logger.warning("invalid_timestamp", extra={"value": timestamp_value, "error": str(exc)})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid timestamp header.",
            ) from exc

        now = time.time()
        if abs(now - request_time) > self._tolerance:
            logger.warning(
                "timestamp_skew",
                extra={"timestamp": request_time, "now": now, "tolerance": self._tolerance},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Timestamp outside allowed skew.",
            )

        message = f"{timestamp_value}:{request.method.upper()}:{request.url.path}".encode("utf-8")
        expected = hmac.new(provided_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning(
                "signature_mismatch",
                extra={"path": request.url.path, "method": request.method},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Signature verification failed.",
            )

    def _resolve_scope(self, request: Request) -> str | None:
        path = request.url.path
        method = request.method.upper()
        if path == "/metrics":
            return "monitor"
        if method in {"GET", "HEAD", "OPTIONS"}:
            return "read"
        return "write"


class MetricsKeyDependency:
    """Validate requests to monitoring endpoints."""

    def __init__(self) -> None:
        settings = get_settings()
        self._header = settings.metrics_key_header
        self._secret = settings.metrics_key

    def __call__(self, request: Request) -> None:
        # Allow API keys with monitor scope first
        scopes = getattr(request.state, "api_key_scopes", set())
        if "monitor" in scopes or "all" in scopes:
            return

        if not self._secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Monitoring disabled.",
            )

        provided = request.headers.get(self._header)
        if not provided or not hmac.compare_digest(provided, self._secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid metrics credential.",
            )


async def purge_expired_api_keys() -> None:
    """Deactivate API keys whose expiry has elapsed."""

    settings = get_settings()
    if not settings.api_key_auto_expiry_enabled:
        return

    SessionLocal = get_session_factory()
    now = datetime.utcnow()
    with SessionLocal() as session:
        expired = (
            session.execute(
                select(ApiKey).where(ApiKey.is_active.is_(True), ApiKey.expires_at.is_not(None), ApiKey.expires_at < now)
            )
            .scalars()
            .all()
        )
        archived: list[ApiKeyArchive] = []
        for record in expired:
            archived_record = _archive_key(session, record, "expired")
            archived.append(archived_record)
        if archived:
            session.commit()
            for archive in archived:
                audit_event(
                    "api_key_archived",
                    api_key_name=archive.name,
                    owner_email=archive.owner_email,
                    reason=archive.archive_reason,
                )
                logger.info(
                    "api_key_deactivated_expiry",
                    extra={"api_key_id": archive.api_key_id, "owner": archive.owner_email},
                )
