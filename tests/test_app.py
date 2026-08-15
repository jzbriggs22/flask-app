"""Tests for the BirdCatch API and frontend routes."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from conftest import post_json, put_json, post_raw, logout  # noqa: E402,F401


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
    post_json(client, "/api/sightings", {"bird_id": 1})
    r = client.get("/api/birdex/1/stats")
    assert r.status_code == 200
    data = r.get_json()
    # Values, not just key presence: the seeded rarity tiers are 15/12/10/7/5.
    assert data["by_rarity"]["common"]["total"] == 15
    assert data["by_rarity"]["legendary"]["total"] == 5
    assert sum(v["total"] for v in data["by_rarity"].values()) == 49
    assert sum(v["caught"] for v in data["by_rarity"].values()) == 1
    assert sum(v["total"] for v in data["by_habitat"].values()) == 49
    assert sum(v["total"] for v in data["by_region"].values()) == 49


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
    # The only user must be rank 1 of 1.
    assert data["rankings"]["xp_rank"] == 1
    assert data["rankings"]["sightings_rank"] == 1
    assert data["rankings"]["total_users"] == 1


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
    data = r.get_json()
    assert sum(data.values()) == 49
    assert set(data) == {"urban", "forest", "wetland", "grassland", "coastal", "mountain"}


def test_regions_endpoint(client):
    r = client.get("/api/birds/regions")
    assert r.status_code == 200
    data = r.get_json()
    assert sum(data.values()) == 49
    assert data["north_america"] > 0


def test_logout(client):
    post_json(client, "/api/register", {
        "username": "logoutuser", "email": "logout@test.com", "password": "password"
    })
    assert client.get("/dashboard", follow_redirects=False).status_code == 200
    r = logout(client)
    assert r.status_code == 200
    # The session must actually be cleared, not merely acknowledged.
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert client.get("/dashboard", follow_redirects=False).status_code == 302


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
    # Non-empty (dedup may return fewer than requested, but never zero).
    assert 1 <= len(data["encounters"]) <= 3
    assert all("bird" in e and "already_caught" in e for e in data["encounters"])
    ids = [e["bird"]["id"] for e in data["encounters"]]
    assert len(ids) == len(set(ids)), "batch encounters must be deduplicated"


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
    logout(client)
    r = post_json(client, "/api/sightings", {"user_id": 1, "bird_id": 1})
    assert r.status_code == 401


def test_sighting_ignores_body_user_id(client):
    """A logged-in attacker cannot credit a sighting to another account via body user_id."""
    post_json(client, "/api/register", {
        "username": "target", "email": "target@test.com", "password": "password"
    })  # user 1
    logout(client)
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
    logout(client)
    post_json(client, "/api/register", {
        "username": "snoop", "email": "snoop@test.com", "password": "password"
    })  # user 2
    r = client.get("/api/sightings/user/1")
    assert r.status_code == 403

    # An unauthenticated caller is rejected outright.
    logout(client)
    r = client.get("/api/sightings/user/1")
    assert r.status_code == 401


def test_register_rejects_non_object_json(client):
    for body in ('["username", "email", "password"]', '"just a string"', "42"):
        r = post_raw(client, "/api/register", body)
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


# ===== Gamification Logic Tests =====

def test_add_xp_level_thresholds(app):
    """add_xp must map cumulative XP onto the right level boundary."""
    from models import User, LEVEL_THRESHOLDS
    with app.app_context():
        u = User(username="lvl", email="lvl@test.com")
        u.set_password("password")
        assert u.add_xp(0) == 1        # 0 XP -> level 1
        u.xp = 0
        assert u.add_xp(99) == 1       # just below the level-2 threshold
        u.xp = 0
        assert u.add_xp(100) == 2      # exactly on the threshold
        u.xp = 0
        assert u.add_xp(299) == 2
        u.xp = 0
        assert u.add_xp(300) == 3
        u.xp = 0
        # Past the final threshold the level caps out.
        assert u.add_xp(LEVEL_THRESHOLDS[-1] + 100_000) == len(LEVEL_THRESHOLDS)


def test_update_streak_arithmetic(app):
    """Streaks extend on consecutive local days, hold same-day, reset on a gap."""
    from datetime import timedelta
    from models import User
    with app.app_context():
        u = User(username="streaker", email="streak@test.com", timezone="UTC")
        u.set_password("password")

        u.update_streak()                       # first ever sighting
        assert u.streak_days == 1
        today = u.last_sighting_date

        u.update_streak()                       # same day: no change
        assert u.streak_days == 1

        u.last_sighting_date = today - timedelta(days=1)
        u.update_streak()                       # consecutive day: extends
        assert u.streak_days == 2

        u.last_sighting_date = today - timedelta(days=5)
        u.update_streak()                       # gap: resets
        assert u.streak_days == 1


def test_streak_uses_user_timezone(app):
    """The day boundary follows the user's timezone, not UTC."""
    from models import User, local_today
    with app.app_context():
        u = User(username="tz", email="tz@test.com", timezone="Pacific/Kiritimati")
        assert u.today() == local_today("Pacific/Kiritimati")
        # Far-apart zones can legitimately disagree on "today".
        assert u.today() >= local_today("Pacific/Niue")


def test_level_up_reported_on_sighting(client, app):
    """Crossing a level threshold reports level_up in the sighting response."""
    from models import db, User
    post_json(client, "/api/register", {
        "username": "climber", "email": "climber@test.com", "password": "password"
    })
    with app.app_context():
        u = User.query.filter_by(username="climber").first()
        u.xp, u.level = 95, 1           # one common catch away from level 2
        db.session.commit()

    r = post_json(client, "/api/sightings", {"bird_id": 1})
    assert r.status_code == 201
    data = r.get_json()
    assert "level_up" in data, "level-up crossing must be reported"
    assert data["level_up"]["old_level"] == 1
    assert data["level_up"]["new_level"] == 2
    assert data["user_stats"]["level"] == 2


def test_level_up_from_challenge_xp_is_reported(client, app):
    """A level crossed by quest-reward XP (not sighting XP) must still report."""
    from models import db, User, DailyChallenge
    post_json(client, "/api/register", {
        "username": "quester", "email": "quester@test.com", "password": "password"
    })
    with app.app_context():
        u = User.query.filter_by(username="quester").first()
        # 10 XP short of level 2 even after the sighting's own XP (22).
        u.xp, u.level = 78, 1
        db.session.query(DailyChallenge).delete()
        db.session.add(DailyChallenge(
            user_id=u.id, date=u.today(), challenge_type="spot_count",
            target_value="1", target_count=1, current_count=0,
            xp_reward=50, description="Spot 1 bird today",
        ))
        db.session.commit()

    r = post_json(client, "/api/sightings", {"bird_id": 1})
    data = r.get_json()
    assert data["completed_challenges"], "the quest should have completed"
    # 78 + 22 = 100 -> level 2 already; the +50 quest XP lands at 150.
    assert data["user_stats"]["xp"] == 150
    assert "level_up" in data
    assert data["user_stats"]["level"] == 2


def test_challenge_completion_awards_xp(client, app):
    """Completing a quest flips it to completed and pays the reward once."""
    from models import db, User, DailyChallenge
    post_json(client, "/api/register", {
        "username": "qc", "email": "qc@test.com", "password": "password"
    })
    with app.app_context():
        u = User.query.filter_by(username="qc").first()
        db.session.query(DailyChallenge).delete()
        db.session.add(DailyChallenge(
            user_id=u.id, date=u.today(), challenge_type="spot_new",
            target_value="new", target_count=1, current_count=0,
            xp_reward=100, description="Discover a new species",
        ))
        db.session.commit()
        before = u.xp

    r = post_json(client, "/api/sightings", {"bird_id": 1})
    data = r.get_json()
    completed = data.get("completed_challenges") or []
    assert len(completed) == 1
    assert completed[0]["completed"] is True
    assert completed[0]["xp_reward"] == 100
    assert data["user_stats"]["xp"] == before + data["xp_breakdown"]["total_xp"] + 100

    # A second sighting must not pay the same quest again.
    xp_after_first = data["user_stats"]["xp"]
    r2 = post_json(client, "/api/sightings", {"bird_id": 2})
    data2 = r2.get_json()
    assert not [c for c in (data2.get("completed_challenges") or [])
                if c["challenge_type"] == "spot_new"]
    assert data2["user_stats"]["xp"] == xp_after_first + data2["xp_breakdown"]["total_xp"]


def test_rarity_achievement_awarded(client):
    """The rarity_* achievement branch actually fires on a rare catch."""
    rare = client.get("/api/birds?rarity=rare").get_json()["birds"][0]
    post_json(client, "/api/register", {
        "username": "rarer", "email": "rarer@test.com", "password": "password"
    })
    r = post_json(client, "/api/sightings", {"bird_id": rare["id"]})
    names = [a["name"] for a in r.get_json().get("new_achievements", [])]
    assert "Rare Discovery" in names


def test_repeat_sighting_earns_reduced_xp(client):
    """Re-logging the same species the same day is damped (anti-farming)."""
    post_json(client, "/api/register", {
        "username": "farmer", "email": "farmer@test.com", "password": "password"
    })
    first = post_json(client, "/api/sightings", {"bird_id": 1}).get_json()
    second = post_json(client, "/api/sightings", {"bird_id": 1}).get_json()

    assert first["xp_breakdown"]["repeat_sighting"] is False
    assert second["xp_breakdown"]["repeat_sighting"] is True
    assert second["xp_breakdown"]["base_xp"] < first["xp_breakdown"]["base_xp"]
    assert second["xp_breakdown"]["streak_bonus"] == 0
    assert second["xp_breakdown"]["total_xp"] < first["xp_breakdown"]["total_xp"]

    # A different species the same day is not penalised.
    other = post_json(client, "/api/sightings", {"bird_id": 2}).get_json()
    assert other["xp_breakdown"]["repeat_sighting"] is False


def test_xp_uses_bird_xp_value(client, app):
    """XP comes from the bird's advertised xp_value, not just its rarity tier."""
    from models import db, Bird
    with app.app_context():
        bird = Bird.query.get(1)
        bird.xp_value = 999
        db.session.commit()

    post_json(client, "/api/register", {
        "username": "xpval", "email": "xpval@test.com", "password": "password"
    })
    data = post_json(client, "/api/sightings", {"bird_id": 1}).get_json()
    assert data["xp_breakdown"]["base_xp"] == 999


# ===== Sighting Read Endpoints =====

def test_user_sightings_pagination(client):
    post_json(client, "/api/register", {
        "username": "pager", "email": "pager@test.com", "password": "password"
    })
    for bird_id in range(1, 6):
        post_json(client, "/api/sightings", {"bird_id": bird_id})

    r = client.get("/api/sightings/user/1?per_page=2&page=1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] == 5
    assert data["pages"] == 3
    assert len(data["sightings"]) == 2

    # per_page is capped, so a huge value cannot dump the table.
    capped = client.get("/api/sightings/user/1?per_page=100000").get_json()
    assert len(capped["sightings"]) == 5


def test_get_single_sighting_owner_only(client):
    post_json(client, "/api/register", {
        "username": "s1", "email": "s1@test.com", "password": "password"
    })
    post_json(client, "/api/sightings", {"bird_id": 1})
    r = client.get("/api/sightings/1")
    assert r.status_code == 200
    assert r.get_json()["bird"]["id"] == 1

    logout(client)
    post_json(client, "/api/register", {
        "username": "s2", "email": "s2@test.com", "password": "password"
    })
    assert client.get("/api/sightings/1").status_code == 403


# ===== Birdex / Leaderboard Fixes =====

def test_birdex_summary_independent_of_show_filter(client):
    """show=uncaught must not zero out the collection summary."""
    post_json(client, "/api/register", {
        "username": "bx", "email": "bx@test.com", "password": "password"
    })
    post_json(client, "/api/sightings", {"bird_id": 1})

    all_view = client.get("/api/birdex/1?show=all").get_json()
    uncaught = client.get("/api/birdex/1?show=uncaught").get_json()
    caught = client.get("/api/birdex/1?show=caught").get_json()

    for view in (all_view, uncaught, caught):
        assert view["caught_species"] == 1
        assert view["total_species"] == 49
        assert view["completion_pct"] == all_view["completion_pct"]
    assert len(uncaught["entries"]) == 48
    assert len(caught["entries"]) == 1


def test_leaderboard_rejects_invalid_sort(client):
    r = client.get("/api/leaderboard?sort=bogus")
    assert r.status_code == 400
    assert "Invalid sort" in r.get_json()["error"]


def test_leaderboard_unique_species_sort(client):
    post_json(client, "/api/register", {
        "username": "one", "email": "one@test.com", "password": "password"
    })
    post_json(client, "/api/sightings", {"bird_id": 1})
    logout(client)
    post_json(client, "/api/register", {
        "username": "three", "email": "three@test.com", "password": "password"
    })
    for bird_id in (1, 2, 3):
        post_json(client, "/api/sightings", {"bird_id": bird_id})

    r = client.get("/api/leaderboard?sort=unique_species")
    assert r.status_code == 200
    board = r.get_json()["leaderboard"]
    assert board[0]["username"] == "three"
    assert board[0]["unique_species"] == 3
    assert board[1]["unique_species"] == 1


def test_leaderboard_limit_is_capped(client):
    r = client.get("/api/leaderboard?limit=1000000")
    assert r.status_code == 200
    assert r.get_json()["limit"] == 100


# ===== Timezone =====

def test_register_with_timezone_and_update(client):
    r = post_json(client, "/api/register", {
        "username": "tzuser", "email": "tzuser@test.com",
        "password": "password", "timezone": "America/New_York",
    })
    assert r.status_code == 201
    assert r.get_json()["user"]["timezone"] == "America/New_York"

    r = put_json(client, "/api/profile/timezone", {"timezone": "Europe/London"})
    assert r.status_code == 200
    assert r.get_json()["user"]["timezone"] == "Europe/London"


def test_register_rejects_invalid_timezone(client):
    r = post_json(client, "/api/register", {
        "username": "badtz", "email": "badtz@test.com",
        "password": "password", "timezone": "Mars/Olympus_Mons",
    })
    assert r.status_code == 400


# ===== CSRF =====

def test_csrf_required_for_authenticated_state_change(client):
    post_json(client, "/api/register", {
        "username": "csrf", "email": "csrf@test.com", "password": "password"
    })
    # Same session, but no CSRF header: rejected.
    import json as _json
    r = client.post("/api/sightings", data=_json.dumps({"bird_id": 1}),
                    content_type="application/json")
    assert r.status_code == 403
    assert "CSRF" in r.get_json()["error"]

    # A wrong token is rejected too.
    r = client.post("/api/sightings", data=_json.dumps({"bird_id": 1}),
                    content_type="application/json",
                    headers={"X-CSRF-Token": "not-the-token"})
    assert r.status_code == 403

    # The correct token succeeds.
    assert post_json(client, "/api/sightings", {"bird_id": 1}).status_code == 201


# ===== Error Handling =====

def test_api_errors_are_json_not_html(client):
    r = client.get("/api/birds/999999")
    assert r.status_code == 404
    assert r.content_type.startswith("application/json")
    assert "error" in r.get_json()

    # Wrong method on a real API route also yields JSON.
    r = client.get("/api/register")
    assert r.status_code == 405
    assert r.content_type.startswith("application/json")


def test_html_pages_still_render_html_errors(client):
    r = client.get("/definitely-not-a-page")
    assert r.status_code == 404
    assert not r.content_type.startswith("application/json")


# ===== Cascade Deletion =====

def test_deleting_user_cascades(client, app):
    """Deleting a user removes their sightings and challenges (GDPR erasure)."""
    from models import db, User, Sighting, DailyChallenge
    post_json(client, "/api/register", {
        "username": "goner", "email": "goner@test.com", "password": "password"
    })
    client.get("/api/challenges")
    post_json(client, "/api/sightings", {"bird_id": 1})

    with app.app_context():
        user = User.query.filter_by(username="goner").first()
        uid = user.id
        assert Sighting.query.filter_by(user_id=uid).count() == 1
        assert DailyChallenge.query.filter_by(user_id=uid).count() > 0

        db.session.delete(user)
        db.session.commit()

        assert User.query.get(uid) is None
        assert Sighting.query.filter_by(user_id=uid).count() == 0
        assert DailyChallenge.query.filter_by(user_id=uid).count() == 0


# ===== Data Integrity =====

def test_daily_challenge_generation_is_idempotent(client, app):
    """Repeated generation never produces a duplicate set for the same day."""
    from models import DailyChallenge, User
    post_json(client, "/api/register", {
        "username": "idem", "email": "idem@test.com", "password": "password"
    })
    for _ in range(4):
        client.get("/api/challenges")

    with app.app_context():
        user = User.query.filter_by(username="idem").first()
        rows = DailyChallenge.query.filter_by(user_id=user.id, date=user.today()).all()
        assert len(rows) == 3
        types = [r.challenge_type for r in rows]
        assert len(types) == len(set(types)), "duplicate challenge types for one day"


def test_quest_descriptions_are_grammatical(app):
    """Generated quest text must not read 'Spot an rare bird'."""
    from routes.challenges import CHALLENGE_TEMPLATES, _build_challenge
    from datetime import date
    rarity_tmpl = next(t for t in CHALLENGE_TEMPLATES if t["type"] == "spot_rarity")
    with app.app_context():
        for _ in range(30):
            ch = _build_challenge(1, date.today(), rarity_tmpl)
            assert "an rare" not in ch.description
            assert "a uncommon" not in ch.description


def test_achievement_icons_are_emoji_not_keys(client):
    """The API serves display-ready emoji so clients never map icon keys."""
    from models import ICON_EMOJI
    post_json(client, "/api/register", {
        "username": "icons", "email": "icons@test.com", "password": "password"
    })
    r = post_json(client, "/api/sightings", {"bird_id": 1})
    achievements = r.get_json()["new_achievements"]
    assert achievements
    for ach in achievements:
        assert ach["icon_emoji"] not in ICON_EMOJI  # not a raw key
        assert ach["icon_emoji"] == ICON_EMOJI.get(ach["icon"])
