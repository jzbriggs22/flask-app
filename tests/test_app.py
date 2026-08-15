"""Tests for the BirdCatch API and frontend routes."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


@pytest.fixture
def client():
    # Pass the in-memory URI THROUGH the factory so the engine binds to it.
    # (Setting config after create_app() is too late: the engine is already bound.)
    app = create_app(test_config={
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        # Sanity check: the suite must never touch the real on-disk database.
        assert ":memory:" in str(db.engine.url), (
            f"Test DB engine bound to {db.engine.url}, expected in-memory"
        )
        db.drop_all()
        db.create_all()
        from seed_data import BIRDS, ACHIEVEMENTS
        from models import Bird, Achievement, RARITY_XP
        for bd in BIRDS:
            db.session.add(Bird(
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
            db.session.add(Achievement(
                name=ad["name"],
                description=ad["description"],
                icon=ad.get("icon"),
                category=ad["category"],
                requirement_type=ad["requirement_type"],
                requirement_value=ad["requirement_value"],
            ))
        db.session.commit()

    with app.test_client() as client:
        yield client


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


# ===== API Tests =====

def test_api_info(client):
    r = client.get("/api/info")
    assert r.status_code == 200
    data = r.get_json()
    assert data["app"] == "BirdCatch - Gamified Birding"


def test_register_and_login(client):
    r = post_json(client, "/api/register", {
        "username": "birder1", "email": "birder1@test.com", "password": "secret123"
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data["user"]["username"] == "birder1"
    assert data["user"]["level"] == 1

    r = post_json(client, "/api/login", {"username": "birder1", "password": "secret123"})
    assert r.status_code == 200

    r = post_json(client, "/api/register", {
        "username": "birder1", "email": "birder1@test.com", "password": "secret123"
    })
    assert r.status_code == 409


def test_list_birds(client):
    r = client.get("/api/birds")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 49

    r = client.get("/api/birds?rarity=legendary")
    data = r.get_json()
    assert data["count"] == 5


def test_bird_search(client):
    r = client.get("/api/birds?search=eagle")
    data = r.get_json()
    assert data["count"] > 0
    assert any("Eagle" in b["common_name"] for b in data["birds"])


def test_log_sighting_and_xp(client):
    post_json(client, "/api/register", {
        "username": "catcher", "email": "catcher@test.com", "password": "password"
    })

    r = post_json(client, "/api/sightings", {
        "bird_id": 1,
        "latitude": 40.7128, "longitude": -74.0060,
        "location_name": "Central Park"
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data["is_new_species"] is True
    assert data["xp_breakdown"]["base_xp"] == 10
    assert data["xp_breakdown"]["new_species_bonus"] == 10
    assert data["user_stats"]["total_sightings"] == 1

    r = post_json(client, "/api/sightings", {"bird_id": 1})
    data = r.get_json()
    assert data["is_new_species"] is False
    assert data["xp_breakdown"]["new_species_bonus"] == 0


def test_sighting_with_session(client):
    """Sighting endpoint works using session user_id (no user_id in body)."""
    post_json(client, "/api/register", {
        "username": "sessionuser", "email": "session@test.com", "password": "password"
    })
    # Session is now set from register; post with just bird_id
    r = post_json(client, "/api/sightings", {"bird_id": 1})
    assert r.status_code == 201
    data = r.get_json()
    assert data["is_new_species"] is True


def test_birdex(client):
    post_json(client, "/api/register", {
        "username": "collector", "email": "collector@test.com", "password": "password"
    })
    post_json(client, "/api/sightings", {"bird_id": 1})

    r = client.get("/api/birdex/1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["caught_species"] == 1
    assert data["total_species"] == 49

    r = client.get("/api/birdex/1?show=caught")
    data = r.get_json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["caught"] is True


def test_birdex_stats(client):
    post_json(client, "/api/register", {
        "username": "stats_user", "email": "stats@test.com", "password": "password"
    })
    r = client.get("/api/birdex/1/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert "by_rarity" in data
    assert "by_habitat" in data
    assert "by_region" in data


def test_leaderboard(client):
    post_json(client, "/api/register", {
        "username": "leader1", "email": "l1@test.com", "password": "password"
    })
    post_json(client, "/api/register", {
        "username": "leader2", "email": "l2@test.com", "password": "password"
    })
    # After registering leader2, the session belongs to leader2, so this
    # sighting is credited to them; they should therefore rank first by XP.
    post_json(client, "/api/sightings", {"bird_id": 1})

    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["leaderboard"]) == 2
    assert data["leaderboard"][0]["rank"] == 1
    # The XP-earning user must actually sort first (not just rank==1 by construction).
    assert data["leaderboard"][0]["username"] == "leader2"
    assert data["leaderboard"][0]["xp"] > data["leaderboard"][1]["xp"]


def test_user_rank(client):
    post_json(client, "/api/register", {
        "username": "ranker", "email": "ranker@test.com", "password": "password"
    })
    r = client.get("/api/leaderboard/user/1")
    assert r.status_code == 200
    data = r.get_json()
    assert "rankings" in data


def test_profile(client):
    post_json(client, "/api/register", {
        "username": "profiler", "email": "profiler@test.com", "password": "password"
    })
    r = client.get("/api/profile/1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["username"] == "profiler"
    assert "achievements" in data


def test_achievements_earned(client):
    post_json(client, "/api/register", {
        "username": "achiever", "email": "achiever@test.com", "password": "password"
    })
    r = post_json(client, "/api/sightings", {"bird_id": 1})
    data = r.get_json()
    assert "new_achievements" in data
    earned_names = [a["name"] for a in data["new_achievements"]]
    assert "First Catch" in earned_names


def test_rarities_endpoint(client):
    r = client.get("/api/birds/rarities")
    assert r.status_code == 200
    data = r.get_json()
    assert "common" in data
    assert "legendary" in data


def test_habitats_endpoint(client):
    r = client.get("/api/birds/habitats")
    assert r.status_code == 200


def test_regions_endpoint(client):
    r = client.get("/api/birds/regions")
    assert r.status_code == 200


def test_logout(client):
    post_json(client, "/api/register", {
        "username": "logoutuser", "email": "logout@test.com", "password": "password"
    })
    r = client.post("/api/logout", content_type="application/json")
    assert r.status_code == 200


# ===== Frontend Route Tests =====

def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"BirdCatch" in r.data


def test_landing_redirects_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "loggedin", "email": "li@test.com", "password": "password"
    })
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers["Location"]


def test_catalog_public(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    assert b"Bird Catalog" in r.data


def test_leaderboard_public(client):
    r = client.get("/leaderboard")
    assert r.status_code == 200
    assert b"Leaderboard" in r.data


def test_dashboard_requires_login(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302


def test_catch_requires_login(client):
    r = client.get("/catch", follow_redirects=False)
    assert r.status_code == 302


def test_birdex_page_requires_login(client):
    r = client.get("/birdex", follow_redirects=False)
    assert r.status_code == 302


def test_achievements_page_requires_login(client):
    r = client.get("/achievements", follow_redirects=False)
    assert r.status_code == 302


def test_dashboard_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "dashuser", "email": "dash@test.com", "password": "password"
    })
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"dashuser" in r.data


def test_catch_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "catchuser", "email": "catch@test.com", "password": "password"
    })
    r = client.get("/catch")
    assert r.status_code == 200
    assert b"Catch a Bird" in r.data


def test_birdex_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "birdexuser", "email": "birdex@test.com", "password": "password"
    })
    r = client.get("/birdex")
    assert r.status_code == 200
    assert b"Birdex" in r.data


def test_achievements_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "achuser", "email": "ach@test.com", "password": "password"
    })
    r = client.get("/achievements")
    assert r.status_code == 200
    assert b"Achievements" in r.data


# ===== New Feature Tests =====

def test_daily_challenges_api(client):
    post_json(client, "/api/register", {
        "username": "questuser", "email": "quest@test.com", "password": "password"
    })
    r = client.get("/api/challenges")
    assert r.status_code == 200
    data = r.get_json()
    assert "challenges" in data
    assert len(data["challenges"]) == 3
    # Calling again returns same challenges (idempotent)
    r2 = client.get("/api/challenges")
    assert len(r2.get_json()["challenges"]) == 3


def test_challenges_require_auth(client):
    r = client.get("/api/challenges")
    assert r.status_code == 401


def test_random_encounter(client):
    r = client.get("/api/encounter")
    assert r.status_code == 200
    data = r.get_json()
    assert "encounter" in data
    assert "common_name" in data["encounter"]
    assert "message" in data


def test_encounter_with_habitat_filter(client):
    r = client.get("/api/encounter?habitat=forest")
    assert r.status_code == 200
    data = r.get_json()
    assert data["encounter"]["habitat"] == "forest"


def test_batch_encounter(client):
    r = client.get("/api/encounter/batch?count=3")
    assert r.status_code == 200
    data = r.get_json()
    assert "encounters" in data
    assert len(data["encounters"]) <= 3


def test_feed_page_public(client):
    r = client.get("/feed")
    assert r.status_code == 200
    assert b"Activity Feed" in r.data


def test_explore_requires_login(client):
    r = client.get("/explore", follow_redirects=False)
    assert r.status_code == 302


def test_challenges_page_requires_login(client):
    r = client.get("/challenges", follow_redirects=False)
    assert r.status_code == 302


def test_explore_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "explorer", "email": "explore@test.com", "password": "password"
    })
    r = client.get("/explore")
    assert r.status_code == 200
    assert b"Explore" in r.data


def test_challenges_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "questpage", "email": "questpage@test.com", "password": "password"
    })
    r = client.get("/challenges")
    assert r.status_code == 200
    assert b"Daily Quests" in r.data


def test_public_profile(client):
    post_json(client, "/api/register", {
        "username": "publicuser", "email": "pub@test.com", "password": "password"
    })
    r = client.get("/profile/1")
    assert r.status_code == 200
    assert b"publicuser" in r.data


def test_challenge_progress_on_sighting(client):
    post_json(client, "/api/register", {
        "username": "challenger", "email": "challenger@test.com", "password": "password"
    })
    # Generate challenges first
    client.get("/api/challenges")
    # Log a sighting
    r = post_json(client, "/api/sightings", {"bird_id": 1})
    assert r.status_code == 201
    # Check challenges updated
    r2 = client.get("/api/challenges")
    data = r2.get_json()
    # At least one challenge should have progress > 0
    has_progress = any(c["current_count"] > 0 for c in data["challenges"])
    assert has_progress


# ===== Security / Regression Tests =====

def test_login_wrong_password_returns_401(client):
    post_json(client, "/api/register", {
        "username": "wp", "email": "wp@test.com", "password": "password"
    })
    r = post_json(client, "/api/login", {"username": "wp", "password": "wrongpass"})
    assert r.status_code == 401
    assert r.get_json()["error"] == "Invalid credentials"


def test_login_unknown_user_returns_401(client):
    r = post_json(client, "/api/login", {"username": "nobody", "password": "whatever"})
    assert r.status_code == 401


def test_sighting_requires_authentication(client):
    """An unauthenticated caller cannot log a sighting, even with a body user_id."""
    post_json(client, "/api/register", {
        "username": "victim", "email": "victim@test.com", "password": "password"
    })
    # Log out so there is no session.
    client.post("/api/logout", content_type="application/json")
    r = post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})
    assert r.status_code == 401


def test_sighting_ignores_body_user_id(client):
    """A logged-in attacker cannot credit a sighting to another account via body user_id."""
    post_json(client, "/api/register", {
        "username": "target", "email": "target@test.com", "password": "password"
    })  # user 1
    client.post("/api/logout", content_type="application/json")
    post_json(client, "/api/register", {
        "username": "attacker", "email": "attacker@test.com", "password": "password"
    })  # user 2, now the active session

    # Attacker tries to award the sighting to the target (user 1).
    r = post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})
    assert r.status_code == 201

    # The sighting must belong to the attacker (session user), not the target.
    assert r.get_json()["user_stats"]["id"] == 2
    target = client.get("/api/profile/1").get_json()
    assert target["total_sightings"] == 0
    attacker = client.get("/api/profile/2").get_json()
    assert attacker["total_sightings"] == 1


def test_user_sightings_owner_only(client):
    post_json(client, "/api/register", {
        "username": "owner", "email": "owner@test.com", "password": "password"
    })  # user 1
    post_json(client, "/api/sightings", {
        "bird_id": 1, "latitude": 1.23, "longitude": 4.56
    })
    # Owner can read their own sightings.
    r = client.get("/api/sightings/user/1")
    assert r.status_code == 200
    assert r.get_json()["total"] == 1

    # A different logged-in user cannot read them (GPS exposure).
    client.post("/api/logout", content_type="application/json")
    post_json(client, "/api/register", {
        "username": "snoop", "email": "snoop@test.com", "password": "password"
    })  # user 2
    r = client.get("/api/sightings/user/1")
    assert r.status_code == 403

    # An unauthenticated caller is rejected outright.
    client.post("/api/logout", content_type="application/json")
    r = client.get("/api/sightings/user/1")
    assert r.status_code == 401


def test_register_rejects_non_object_json(client):
    for body in ('["username", "email", "password"]', '"just a string"', "42"):
        r = client.post("/api/register", data=body, content_type="application/json")
        assert r.status_code == 400


def test_register_rejects_empty_and_short_credentials(client):
    r = post_json(client, "/api/register", {"username": "", "email": "", "password": ""})
    assert r.status_code == 400
    r = post_json(client, "/api/register", {
        "username": "shorty", "email": "s@test.com", "password": "abc"
    })
    assert r.status_code == 400


def test_sightings_rejects_bad_types(client):
    post_json(client, "/api/register", {
        "username": "typer", "email": "typer@test.com", "password": "password"
    })
    # Non-integer bird_id -> 400, not 500.
    r = post_json(client, "/api/sightings", {"bird_id": [1, 2]})
    assert r.status_code == 400
    # Non-numeric latitude -> 400, not 500.
    r = post_json(client, "/api/sightings", {"bird_id": 1, "latitude": "not-a-number"})
    assert r.status_code == 400


def test_stale_session_redirects_not_500(client):
    """A session pointing at a non-existent user must not 500 the page."""
    with client.session_transaction() as sess:
        sess["user_id"] = 999999
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302


def test_avian_scholar_is_earnable(client):
    """No unique_species achievement may require more species than exist."""
    total_birds = client.get("/api/birds").get_json()["count"]
    from seed_data import ACHIEVEMENTS
    species_reqs = [a["requirement_value"] for a in ACHIEVEMENTS
                    if a["requirement_type"] == "unique_species"]
    assert max(species_reqs) <= total_birds


def test_secret_key_guard_refuses_prod_default(monkeypatch):
    """create_app must refuse the dev fallback secret when FLASK_ENV=production."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError):
        create_app()
