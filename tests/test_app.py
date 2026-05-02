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
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True

    with app.app_context():
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
        "username": "catcher", "email": "catcher@test.com", "password": "pass"
    })

    r = post_json(client, "/api/sightings", {
        "user_id": 1, "bird_id": 1,
        "latitude": 40.7128, "longitude": -74.0060,
        "location_name": "Central Park"
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data["is_new_species"] is True
    assert data["xp_breakdown"]["base_xp"] == 10
    assert data["xp_breakdown"]["new_species_bonus"] == 10
    assert data["user_stats"]["total_sightings"] == 1

    r = post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})
    data = r.get_json()
    assert data["is_new_species"] is False
    assert data["xp_breakdown"]["new_species_bonus"] == 0


def test_sighting_with_session(client):
    """Sighting endpoint works using session user_id (no user_id in body)."""
    post_json(client, "/api/register", {
        "username": "sessionuser", "email": "session@test.com", "password": "pass"
    })
    # Session is now set from register; post with just bird_id
    r = post_json(client, "/api/sightings", {"bird_id": 1})
    assert r.status_code == 201
    data = r.get_json()
    assert data["is_new_species"] is True


def test_birdex(client):
    post_json(client, "/api/register", {
        "username": "collector", "email": "collector@test.com", "password": "pass"
    })
    post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})

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
        "username": "stats_user", "email": "stats@test.com", "password": "pass"
    })
    r = client.get("/api/birdex/1/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert "by_rarity" in data
    assert "by_habitat" in data
    assert "by_region" in data


def test_leaderboard(client):
    post_json(client, "/api/register", {
        "username": "leader1", "email": "l1@test.com", "password": "pass"
    })
    post_json(client, "/api/register", {
        "username": "leader2", "email": "l2@test.com", "password": "pass"
    })
    post_json(client, "/api/sightings", {"user_id": 2, "bird_id": 1})

    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["leaderboard"]) == 2
    assert data["leaderboard"][0]["rank"] == 1


def test_user_rank(client):
    post_json(client, "/api/register", {
        "username": "ranker", "email": "ranker@test.com", "password": "pass"
    })
    r = client.get("/api/leaderboard/user/1")
    assert r.status_code == 200
    data = r.get_json()
    assert "rankings" in data


def test_profile(client):
    post_json(client, "/api/register", {
        "username": "profiler", "email": "profiler@test.com", "password": "pass"
    })
    r = client.get("/api/profile/1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["username"] == "profiler"
    assert "achievements" in data


def test_achievements_earned(client):
    post_json(client, "/api/register", {
        "username": "achiever", "email": "achiever@test.com", "password": "pass"
    })
    r = post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})
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
        "username": "logoutuser", "email": "logout@test.com", "password": "pass"
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
        "username": "loggedin", "email": "li@test.com", "password": "pass"
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
        "username": "dashuser", "email": "dash@test.com", "password": "pass"
    })
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"dashuser" in r.data


def test_catch_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "catchuser", "email": "catch@test.com", "password": "pass"
    })
    r = client.get("/catch")
    assert r.status_code == 200
    assert b"Catch a Bird" in r.data


def test_birdex_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "birdexuser", "email": "birdex@test.com", "password": "pass"
    })
    r = client.get("/birdex")
    assert r.status_code == 200
    assert b"Birdex" in r.data


def test_achievements_page_accessible_when_logged_in(client):
    post_json(client, "/api/register", {
        "username": "achuser", "email": "ach@test.com", "password": "pass"
    })
    r = client.get("/achievements")
    assert r.status_code == 200
    assert b"Achievements" in r.data
