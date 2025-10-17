"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import api
from .config import get_settings
from .database import create_all, get_session, init_engine
from .logging_config import configure_logging
from .models import MemoryEdge, MemoryNode, MemoryTrace, Task, User
from .schemas import Message
from .security import (
    APIKeyAuthDependency,
    MetricsKeyDependency,
    RateLimitDependency,
    purge_expired_api_keys,
)


def create_app() -> FastAPI:
    configure_logging()
    init_engine()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        create_all()
        settings = get_settings()
        expiry_task: asyncio.Task | None = None
        if settings.api_key_auto_expiry_enabled:
            expiry_task = asyncio.create_task(_expiry_loop(settings.api_key_expiry_check_seconds))
        try:
            yield
        finally:
            if expiry_task:
                expiry_task.cancel()
                with suppress(asyncio.CancelledError):
                    await expiry_task

    settings = get_settings()
    app = FastAPI(
        title="Task Registry API",
        version="1.0.0",
        description=(
            "REST endpoints for agents that require explicit task and user state."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.metrics_cache = {"content": None, "expires": 0.0}

    rate_limit_dependency = RateLimitDependency()
    auth_dependency = APIKeyAuthDependency()
    optional_auth_dependency = APIKeyAuthDependency(require=False)

    @app.get("/healthz", response_model=Message, dependencies=[Depends(rate_limit_dependency)])
    def healthcheck() -> Message:
        return Message(detail="ok")

    metrics_dependency = MetricsKeyDependency()

    @app.get(
        "/metrics",
        dependencies=[Depends(optional_auth_dependency), Depends(metrics_dependency)],
    )
    def metrics(session: Session = Depends(get_session)) -> Response:
        """Expose Prometheus-style metrics for monitoring."""

        now = time.time()
        cache_seconds = settings.metrics_cache_seconds
        cache = app.state.metrics_cache
        if cache_seconds and cache.get("content") and cache.get("expires", 0.0) > now:
            return Response(content=cache["content"], media_type="text/plain")

        counts = {
            "tasks": session.execute(select(func.count()).select_from(Task)).scalar_one(),
            "users": session.execute(select(func.count()).select_from(User)).scalar_one(),
            "memory_nodes": session.execute(select(func.count()).select_from(MemoryNode)).scalar_one(),
            "memory_edges": session.execute(select(func.count()).select_from(MemoryEdge)).scalar_one(),
            "memory_traces": session.execute(select(func.count()).select_from(MemoryTrace)).scalar_one(),
        }
        status_counts = dict(
            session.execute(select(Task.status, func.count()).group_by(Task.status)).all()
        )
        lines = [
            "# HELP task_registry_total_tasks Total number of tasks registered",
            "# TYPE task_registry_total_tasks gauge",
            f"task_registry_total_tasks {counts['tasks']}",
            "# HELP task_registry_total_users Total number of users",
            "# TYPE task_registry_total_users gauge",
            f"task_registry_total_users {counts['users']}",
            "# HELP task_registry_memory_nodes Total memory nodes",
            "# TYPE task_registry_memory_nodes gauge",
            f"task_registry_memory_nodes {counts['memory_nodes']}",
            "# HELP task_registry_memory_edges Total memory edges",
            "# TYPE task_registry_memory_edges gauge",
            f"task_registry_memory_edges {counts['memory_edges']}",
            "# HELP task_registry_memory_traces Total memory traces",
            "# TYPE task_registry_memory_traces gauge",
            f"task_registry_memory_traces {counts['memory_traces']}",
        ]
        if status_counts:
            lines.extend(
                [
                    "# HELP task_registry_tasks_status_total Task totals grouped by status",
                    "# TYPE task_registry_tasks_status_total gauge",
                ]
            )
        for status, total in status_counts.items():
            metric_name = f"task_registry_tasks_status_total{{status=\"{status}\"}}"
            lines.append(metric_name + f" {total}")

        payload = "\n".join(lines) + "\n"
        if cache_seconds:
            cache["content"] = payload
            cache["expires"] = now + cache_seconds
        return Response(content=payload, media_type="text/plain")

    app.state.rate_limiter = rate_limit_dependency
    app.include_router(
        api.router,
        dependencies=[Depends(rate_limit_dependency), Depends(auth_dependency)],
    )

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        security_schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        security_schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "name": settings.api_key_header,
            "in": "header",
            "description": "Plaintext API key required for authenticated calls.",
        }

        security_requirement = [{"ApiKeyAuth": []}]
        if settings.api_hmac_enabled:
            security_schemes["HMACSignature"] = {
                "type": "apiKey",
                "name": settings.api_signature_header,
                "in": "header",
                "description": (
                    "Hex-encoded HMAC signature when HMAC protection is enabled. "
                    f"Must pair with {settings.api_timestamp_header}."
                ),
            }
            parameters = schema["components"].setdefault("parameters", {})
            parameters[settings.api_timestamp_header] = {
                "name": settings.api_timestamp_header,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": "UNIX timestamp used in the HMAC signature payload.",
            }
            security_requirement = [{"ApiKeyAuth": [], "HMACSignature": []}]

        for path, operations in schema.get("paths", {}).items():
            if path in {"/healthz", "/metrics"}:
                continue
            for method, operation in operations.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                    continue
                operation.setdefault("security", security_requirement)
                if settings.api_hmac_enabled:
                    params = operation.setdefault("parameters", [])
                    if not any(param.get("name") == settings.api_timestamp_header for param in params):
                        params.append({"$ref": f"#/components/parameters/{settings.api_timestamp_header}"})

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[assignment]

    return app


app = create_app()


async def _expiry_loop(interval_seconds: int) -> None:
    while True:
        await purge_expired_api_keys()
        await asyncio.sleep(interval_seconds)
