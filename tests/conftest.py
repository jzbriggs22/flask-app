import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path):
    test_db = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_BURST"] = "100"
    os.environ.setdefault("API_AUTH_ENABLED", "true")
    os.environ["METRICS_KEY"] = "metrics-secret"
    os.environ["METRICS_CACHE_SECONDS"] = "0"
    os.environ["RATE_LIMIT_BACKEND"] = "memory"
    os.environ["AUDIT_LOG_ENABLED"] = "false"
    os.environ["AUDIT_QUEUE_ENABLED"] = "false"
    os.environ.pop("METRICS_CACHE_OVERRIDES", None)

    from app import database
    from app.audit_queue import reset_audit_queue_cache
    from app.config import reset_settings_cache
    from app.models import ApiKey
    from app.security import hash_api_key

    reset_settings_cache()
    reset_audit_queue_cache()
    database.init_engine(str(os.environ["DATABASE_URL"]))
    from app import main

    app = main.create_app()

    engine = database.get_engine()
    database.Base.metadata.drop_all(bind=engine)
    database.Base.metadata.create_all(bind=engine)

    raw_key = secrets.token_urlsafe(16)
    SessionLocal = database.get_session_factory()
    with SessionLocal() as session:
        session.add(
            ApiKey(
                name="pytest-suite",
                key_hash=hash_api_key(raw_key),
                owner_email="qa@example.com",
                scopes=["read", "write", "monitor"],
            )
        )
        session.commit()

    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": raw_key})
        yield test_client


@pytest.fixture(scope="session")
def redis_server():
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server binary not available")

    port = 6390
    process = subprocess.Popen(
        [binary, "--save", "", "--appendonly", "no", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        import redis
    except ImportError:  # pragma: no cover - redis is installed via requirements
        process.terminate()
        raise

    client = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
    for _ in range(50):
        try:
            client.ping()
            break
        except redis.exceptions.ConnectionError:
            time.sleep(0.1)
    else:
        process.terminate()
        pytest.skip("redis-server failed to start")

    yield f"redis://127.0.0.1:{port}/0"

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
        process.kill()
