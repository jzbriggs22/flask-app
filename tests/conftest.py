"""Shared pytest fixtures for the BirdCatch test suite."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import db  # noqa: E402


@pytest.fixture
def app():
    """An application bound to a throwaway in-memory database.

    The URI is passed THROUGH the factory: setting it afterwards would be too
    late, because Flask-SQLAlchemy binds the engine during init_app, and the
    suite would silently run against (and wipe) the real instance/birding.db.
    """
    application = create_app(test_config={
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    })

    with application.app_context():
        assert ":memory:" in str(db.engine.url), (
            f"Test DB engine bound to {db.engine.url}, expected in-memory"
        )
        db.drop_all()
        db.create_all()
        _seed(db)

    return application


def _seed(database):
    from seed_data import BIRDS, ACHIEVEMENTS
    from models import Bird, Achievement, RARITY_XP

    for bd in BIRDS:
        database.session.add(Bird(
            common_name=bd["common_name"],
            scientific_name=bd["scientific_name"],
            rarity=bd["rarity"],
            family=bd.get("family"),
            habitat=bd.get("habitat"),
            region=bd.get("region"),
            description=bd.get("description"),
            xp_value=RARITY_XP.get(bd["rarity"], 10),
        ))
    for ad in ACHIEVEMENTS:
        database.session.add(Achievement(
            name=ad["name"],
            description=ad["description"],
            icon=ad.get("icon"),
            category=ad["category"],
            requirement_type=ad["requirement_type"],
            requirement_value=ad["requirement_value"],
        ))
    database.session.commit()


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        yield test_client


# ---------- CSRF-aware request helpers ----------
# State-changing API calls from an authenticated session must echo the CSRF
# token, exactly as the browser frontend does.

def csrf_token(client):
    with client.session_transaction() as sess:
        return sess.get("csrf_token")


def _headers(client, extra=None):
    headers = dict(extra or {})
    token = csrf_token(client)
    if token:
        headers.setdefault("X-CSRF-Token", token)
    return headers


def post_json(client, url, data, headers=None):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers=_headers(client, headers),
    )


def put_json(client, url, data, headers=None):
    return client.put(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers=_headers(client, headers),
    )


def post_raw(client, url, body, headers=None):
    """POST a raw (possibly malformed) body with the JSON content type."""
    return client.post(
        url,
        data=body,
        content_type="application/json",
        headers=_headers(client, headers),
    )


def logout(client):
    return client.post(
        "/api/logout",
        content_type="application/json",
        headers=_headers(client),
    )
