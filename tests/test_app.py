import asyncio
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.config import reset_settings_cache
from app.models import ApiKey, ApiKeyArchive
from app.security import hash_api_key, purge_expired_api_keys


def test_missing_api_key_rejected(tmp_path):
    if os.getenv("API_AUTH_ENABLED", "true").lower() != "true":
        pytest.skip("API auth disabled")

    test_db = tmp_path / "noauth.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    os.environ["API_HMAC_ENABLED"] = "false"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    engine = database.get_engine()
    database.Base.metadata.create_all(bind=engine)

    from app import main

    app = main.create_app()

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/users")
        assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_create_and_list_users(client):
    response = client.post(
        "/users",
        json={"name": "Marie Curie", "email": "marie@example.com"},
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "Marie Curie"

    response = client.get("/users")
    assert response.status_code == HTTPStatus.OK
    users = response.json()
    assert len(users) == 1
    assert users[0]["email"] == "marie@example.com"


def test_duplicate_user_email_returns_conflict(client):
    payload = {"name": "Ada Lovelace", "email": "ada@example.com"}
    client.post("/users", json=payload)
    duplicate = client.post("/users", json=payload)
    assert duplicate.status_code == HTTPStatus.CONFLICT


def test_create_and_update_task(client):
    user_response = client.post(
        "/users", json={"name": "Task Owner", "email": "owner@example.com"}
    )
    owner_id = user_response.json()["id"]

    response = client.post(
        "/tasks",
        json={
            "task_id": "TASK_001",
            "name": "Initial planning",
            "project": "PROJECT_ALPHA",
            "status": "pending",
            "context": {"priority": "high"},
            "dependencies": [],
            "owner_id": owner_id,
        },
    )
    assert response.status_code == HTTPStatus.CREATED

    update_response = client.patch(
        "/tasks/TASK_001",
        json={"status": "in_progress", "dependencies": ["TASK_000"]},
    )
    assert update_response.status_code == HTTPStatus.OK
    updated = update_response.json()
    assert updated["status"] == "in_progress"
    assert updated["dependencies"] == ["TASK_000"]


def test_bulk_update_requires_existing_tasks(client):
    client.post(
        "/tasks",
        json={
            "task_id": "TASK_100",
            "name": "Bootstrap",
            "project": "PROJECT_X",
            "status": "pending",
        },
    )

    response = client.post(
        "/tasks/bulk-update",
        json={"updates": [{"task_id": "TASK_999", "status": "complete"}]},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_memory_node_lifecycle(client):
    client.post("/tasks", json={"task_id": "task_mem_1", "name": "Draft memory"})

    create_resp = client.post(
        "/memory/nodes",
        json={
            "node_id": "memory_alpha",
            "title": "User preference summary",
            "summary": "Alice prefers async updates",
            "originating_task_ref": "task_mem_1",
        },
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.json()
    node_payload = create_resp.json()
    assert node_payload["node_id"] == "MEMORY_ALPHA"
    assert node_payload["originating_task_ref"] == "TASK_MEM_1"

    list_resp = client.get("/memory/nodes", params={"task": "task_mem_1"})
    assert list_resp.status_code == HTTPStatus.OK
    assert len(list_resp.json()) == 1

    update_resp = client.patch(
        "/memory/nodes/MEMORY_ALPHA",
        json={"summary": "Alice switched to realtime", "originating_task_ref": None},
    )
    assert update_resp.status_code == HTTPStatus.OK
    updated = update_resp.json()
    assert updated["summary"] == "Alice switched to realtime"
    assert updated["originating_task_ref"] is None

    delete_resp = client.delete("/memory/nodes/MEMORY_ALPHA")
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT


def test_memory_edge_and_graph(client):
    client.post("/tasks", json={"task_id": "task_src", "name": "Source task"})
    client.post("/tasks", json={"task_id": "task_dst", "name": "Target task"})

    client.post(
        "/memory/nodes",
        json={"node_id": "node_src", "title": "Context A", "originating_task_ref": "task_src"},
    )
    client.post(
        "/memory/nodes",
        json={"node_id": "node_dst", "title": "Context B", "originating_task_ref": "task_dst"},
    )

    edge_resp = client.post(
        "/memory/edges",
        json={
            "edge_id": "edge_link",
            "relation": "supports",
            "source_node_ref": "node_src",
            "target_node_ref": "node_dst",
            "target_task_ref": "task_dst",
        },
    )
    assert edge_resp.status_code == HTTPStatus.CREATED, edge_resp.json()
    edge_payload = edge_resp.json()
    assert edge_payload["edge_id"] == "EDGE_LINK"
    assert edge_payload["source_node_ref"] == "NODE_SRC"
    assert edge_payload["target_task_ref"] == "TASK_DST"

    graph_resp = client.get("/memory/graph", params={"task": "task_dst"})
    assert graph_resp.status_code == HTTPStatus.OK
    graph = graph_resp.json()
    assert {node["node_id"] for node in graph["nodes"]} >= {"NODE_DST"}
    assert any(edge["edge_id"] == "EDGE_LINK" for edge in graph["edges"])

    update_edge = client.patch(
        "/memory/edges/EDGE_LINK",
        json={"relation": "unblocks", "weight": 2.5, "target_task_ref": None},
    )
    assert update_edge.status_code == HTTPStatus.OK
    assert update_edge.json()["relation"] == "unblocks"
    assert update_edge.json()["target_task_ref"] is None

    delete_edge = client.delete("/memory/edges/EDGE_LINK")
    assert delete_edge.status_code == HTTPStatus.NO_CONTENT


def test_memory_trace_flow(client):
    client.post("/tasks", json={"task_id": "task_trace", "name": "Trace task"})
    client.post(
        "/memory/nodes",
        json={
            "node_id": "node_trace",
            "title": "Trace Node",
            "originating_task_ref": "task_trace",
        },
    )

    create_resp = client.post(
        "/memory/traces",
        json={
            "trace_id": "trace_001",
            "source": "agent_pipeline",
            "payload": {"event": "analysis"},
            "task_ref": "task_trace",
            "node_ref": "node_trace",
        },
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    trace_payload = create_resp.json()
    assert trace_payload["trace_id"] == "TRACE_001"
    assert trace_payload["node_ref"] == "NODE_TRACE"

    list_resp = client.get("/memory/traces", params={"task": "task_trace"})
    assert list_resp.status_code == HTTPStatus.OK
    assert len(list_resp.json()) == 1

    detail_resp = client.get("/memory/traces/TRACE_001")
    assert detail_resp.status_code == HTTPStatus.OK
    assert detail_resp.json()["source"] == "agent_pipeline"

    timeline_resp = client.get("/tasks/TASK_TRACE/timeline")
    assert timeline_resp.status_code == HTTPStatus.OK
    assert timeline_resp.json()[0]["trace_id"] == "TRACE_001"


def test_rate_limit_enforced(tmp_path):
    test_db = tmp_path / "limit.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["RATE_LIMIT_BURST"] = "0"
    os.environ["METRICS_KEY"] = "metrics-secret"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    engine = database.get_engine()
    database.Base.metadata.create_all(bind=engine)

    from app import main

    app = main.create_app()

    engine = database.get_engine()
    database.Base.metadata.drop_all(bind=engine)
    database.Base.metadata.create_all(bind=engine)

    with TestClient(app) as limiter_client:
        first = limiter_client.get("/healthz")
        assert first.status_code == HTTPStatus.OK
        second = limiter_client.get("/healthz")
        assert second.status_code == HTTPStatus.OK
        third = limiter_client.get("/healthz")
        assert third.status_code == HTTPStatus.TOO_MANY_REQUESTS

    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    reset_settings_cache()


def test_read_only_scope_blocks_mutations(client):
    raw_key = secrets.token_urlsafe(16)
    SessionLocal = database.get_session_factory()
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="read-only",
                key_hash=hash_api_key(raw_key),
                scopes=["read"],
                is_active=True,
            )
        )
        session.commit()

    response = client.post(
        "/users",
        json={"name": "Blocked", "email": "blocked@example.com"},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


def test_scope_errors_increment_analytics(client):
    raw_key = secrets.token_urlsafe(16)
    SessionLocal = database.get_session_factory()
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="analytics",
                key_hash=hash_api_key(raw_key),
                scopes=["read"],
                is_active=True,
            )
        )
        session.commit()

    client.post(
        "/users",
        json={"name": "Analytics", "email": "analytics@example.com"},
        headers={"X-API-Key": raw_key},
    )

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == "analytics")).scalar_one()
        assert record.error_count == 1
        assert record.request_count == 1
        assert record.last_error_reason.startswith("missing_scope")


def test_metrics_requires_credential(client):
    # monitor scope key should be allowed
    response = client.get("/metrics")
    assert response.status_code == HTTPStatus.OK
    assert "task_registry_total_tasks" in response.text

    # Missing API key but valid metrics key
    os.environ["API_AUTH_ENABLED"] = "false"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    reset_settings_cache()
    from app import main

    app = main.create_app()
    with TestClient(app) as metrics_client:
        resp = metrics_client.get("/metrics", headers={"X-Metrics-Key": "metrics-secret"})
        assert resp.status_code == HTTPStatus.OK
        denied = metrics_client.get("/metrics")
        assert denied.status_code == HTTPStatus.UNAUTHORIZED
    os.environ["API_AUTH_ENABLED"] = "true"
    reset_settings_cache()


def test_hmac_signature_required(tmp_path):
    test_db = tmp_path / "hmac.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["API_HMAC_ENABLED"] = "true"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    os.environ["METRICS_KEY"] = "metrics-secret"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))

    from app import main

    app = main.create_app()
    database.Base.metadata.create_all(bind=database.get_engine())
    SessionLocal = database.get_session_factory()
    raw_key = secrets.token_urlsafe(16)
    with SessionLocal() as session:
        session.add(ApiKey(name="hmac", key_hash=hash_api_key(raw_key), scopes=["read", "write"]))
        session.commit()

    with TestClient(app) as hmac_client:
        ts = str(time.time())
        signature = hmac.new(
            raw_key.encode("utf-8"),
            f"{ts}:GET:/users".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        ok = hmac_client.get(
            "/users",
            headers={
                "X-API-Key": raw_key,
                "X-Timestamp": ts,
                "X-Signature": signature,
            },
        )
        assert ok.status_code in {HTTPStatus.OK, HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND}

        missing = hmac_client.get(
            "/users",
            headers={"X-API-Key": raw_key},
        )
        assert missing.status_code == HTTPStatus.UNAUTHORIZED

    os.environ["API_HMAC_ENABLED"] = "false"
    reset_settings_cache()


def test_expired_keys_are_deactivated(tmp_path):
    test_db = tmp_path / "expired.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    os.environ["METRICS_KEY"] = "metrics-secret"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))

    from app import main

    app = main.create_app()
    database.Base.metadata.create_all(bind=database.get_engine())
    SessionLocal = database.get_session_factory()
    raw_key = secrets.token_urlsafe(16)
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="expired",
                key_hash=hash_api_key(raw_key),
                scopes=["read"],
                is_active=True,
                expires_at=datetime.utcnow() - timedelta(minutes=5),
            )
        )
        session.commit()

    with TestClient(app) as expired_client:
        response = expired_client.get("/users", headers={"X-API-Key": raw_key})
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == "expired")).scalar_one_or_none()
        if record:
            # Expiry worker may not have archived yet; ensure metrics recorded.
            assert record.is_active is False
            assert record.error_count == 1
            assert record.request_count == 1
            assert record.last_error_reason == "expired"
        else:
            archive = (
                session.execute(select(ApiKeyArchive).where(ApiKeyArchive.name == "expired"))
                .scalars()
                .one()
            )
            assert archive.archive_reason == "expired"


def test_purge_expired_api_keys(tmp_path):
    test_db = tmp_path / "purge.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    engine = database.get_engine()
    database.Base.metadata.create_all(bind=engine)

    SessionLocal = database.get_session_factory()
    raw_key = secrets.token_urlsafe(16)
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="stale",
                key_hash=hash_api_key(raw_key),
                scopes=["read"],
                is_active=True,
                expires_at=datetime.utcnow() - timedelta(days=1),
            )
        )
        session.commit()

    asyncio.run(purge_expired_api_keys())

    with SessionLocal() as session:
        record = session.execute(select(ApiKey).where(ApiKey.name == "stale")).scalar_one_or_none()
        assert record is None
        archived = (
            session.execute(select(ApiKeyArchive).where(ApiKeyArchive.name == "stale"))
            .scalars()
            .one()
        )
        assert archived.archive_reason == "expired"


def test_metrics_cache_respects_ttl(tmp_path):
    test_db = tmp_path / "metrics-cache.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    os.environ["METRICS_KEY"] = "metrics-secret"
    os.environ["METRICS_CACHE_SECONDS"] = "60"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    from app import main

    app = main.create_app()
    engine = database.get_engine()
    database.Base.metadata.drop_all(bind=engine)
    database.Base.metadata.create_all(bind=engine)

    SessionLocal = database.get_session_factory()
    raw_key = secrets.token_urlsafe(16)
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="metrics",
                key_hash=hash_api_key(raw_key),
                scopes=["read", "write", "monitor"],
            )
        )
        session.commit()

    def metric_value(content: str, metric: str) -> float:
        for line in content.splitlines():
            if line.startswith(metric + " "):
                return float(line.split(" ")[1])
        raise AssertionError(f"Metric {metric} not present")

    with TestClient(app) as metrics_client:
        metrics_client.headers.update({"X-API-Key": raw_key})
        first = metrics_client.get("/metrics")
        assert first.status_code == HTTPStatus.OK
        first_users = metric_value(first.text, "task_registry_total_users")

        metrics_client.post(
            "/users",
            json={"name": "Cache", "email": "cache@example.com"},
        )

        second = metrics_client.get("/metrics")
        assert metric_value(second.text, "task_registry_total_users") == first_users

        app.state.metrics_cache["expires"] = time.time() - 1
        third = metrics_client.get("/metrics")
        assert metric_value(third.text, "task_registry_total_users") == first_users + 1

    os.environ["METRICS_CACHE_SECONDS"] = "0"
    reset_settings_cache()


def test_openapi_includes_hmac_headers(tmp_path):
    test_db = tmp_path / "openapi.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["API_HMAC_ENABLED"] = "true"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    from app import main

    app = main.create_app()
    schema = app.openapi()
    assert "HMACSignature" in schema["components"]["securitySchemes"]
    timestamp_header = schema["components"]["parameters"]["X-Timestamp"]
    assert timestamp_header["required"] is True
    users_get = schema["paths"]["/users"]["get"]
    assert any("HMACSignature" in sec for sec in users_get["security"])
    assert any(
        ref.get("$ref") == "#/components/parameters/X-Timestamp" for ref in users_get["parameters"]
    )

    os.environ["API_HMAC_ENABLED"] = "false"
    reset_settings_cache()


def test_redis_rate_limiter_backend(redis_server, tmp_path):
    test_db = tmp_path / "redis.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["RATE_LIMIT_BURST"] = "0"
    os.environ["RATE_LIMIT_BACKEND"] = "redis"
    os.environ["RATE_LIMIT_REDIS_URL"] = redis_server
    os.environ["METRICS_KEY"] = "metrics-secret"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    os.environ["AUDIT_LOG_ENABLED"] = "false"

    reset_settings_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    from app import main

    app = main.create_app()
    engine = database.get_engine()
    database.Base.metadata.drop_all(bind=engine)
    database.Base.metadata.create_all(bind=engine)

    SessionLocal = database.get_session_factory()
    raw_key = secrets.token_urlsafe(16)
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="redis", key_hash=hash_api_key(raw_key), scopes=["read"], is_active=True
            )
        )
        session.commit()

    with TestClient(app) as rate_client:
        rate_client.headers.update({"X-API-Key": raw_key})
        assert rate_client.get("/users").status_code in {HTTPStatus.OK, HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND}
        assert rate_client.get("/users").status_code in {HTTPStatus.OK, HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND}
        blocked = rate_client.get("/users")
        assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS

    os.environ["RATE_LIMIT_BACKEND"] = "memory"
    os.environ.pop("RATE_LIMIT_REDIS_URL", None)
    reset_settings_cache()


def test_vault_store_is_noop_when_disabled():
    from app.vault import store_api_key_secret

    reset_settings_cache()
    assert store_api_key_secret("noop", "secret", {"env": "test"}) is False
