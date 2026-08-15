import os
import warnings
from flask import Flask, jsonify
from models import db, Bird, Achievement, RARITY_XP
from seed_data import BIRDS, ACHIEVEMENTS
from routes import (
    auth_bp, birds_bp, sightings_bp, birdex_bp, leaderboard_bp,
    challenges_bp, encounter_bp, pages_bp,
)

_DEV_SECRET = "dev-secret-key-change-in-production"


def _resolve_secret_key(test_config):
    """Return a secret key, refusing to boot with the dev fallback in production.

    Precedence: explicit test_config > SECRET_KEY env var > dev fallback.
    The dev fallback is refused when FLASK_ENV=production so a misconfigured
    deployment fails loudly instead of silently signing cookies with a public key.
    """
    if test_config and test_config.get("SECRET_KEY"):
        return test_config["SECRET_KEY"]
    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        return env_secret
    if os.environ.get("FLASK_ENV", "").lower() == "production":
        raise RuntimeError(
            "SECRET_KEY environment variable must be set in production. "
            "Refusing to start with the insecure development fallback."
        )
    warnings.warn(
        "SECRET_KEY not set; using the insecure development fallback. "
        "Set SECRET_KEY (and FLASK_ENV=production) before deploying.",
        stacklevel=2,
    )
    return _DEV_SECRET


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///birding.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = _resolve_secret_key(test_config)
    # Harden session cookies (Secure is enabled outside debug/testing).
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    if test_config:
        app.config.update(test_config)

    if not (app.debug or app.testing):
        app.config["SESSION_COOKIE_SECURE"] = True

    db.init_app(app)

    # API blueprints
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(birds_bp, url_prefix="/api")
    app.register_blueprint(sightings_bp, url_prefix="/api")
    app.register_blueprint(birdex_bp, url_prefix="/api")
    app.register_blueprint(leaderboard_bp, url_prefix="/api")
    app.register_blueprint(challenges_bp, url_prefix="/api")
    app.register_blueprint(encounter_bp, url_prefix="/api")

    # Frontend pages
    app.register_blueprint(pages_bp)

    @app.route("/api/info")
    def api_info():
        return jsonify({
            "app": "BirdCatch - Gamified Birding",
            "version": "0.1.0",
            "description": "Gotta spot 'em all! A Pokemon-style birding adventure.",
            "endpoints": {
                "auth": {
                    "POST /api/register": "Create a new account",
                    "POST /api/login": "Log in",
                    "GET /api/profile/<user_id>": "View user profile",
                },
                "birds": {
                    "GET /api/birds": "Browse all birds (filter by rarity, habitat, region, search)",
                    "GET /api/birds/<id>": "Bird details",
                    "GET /api/birds/rarities": "Bird counts by rarity",
                    "GET /api/birds/habitats": "Bird counts by habitat",
                    "GET /api/birds/regions": "Bird counts by region",
                },
                "sightings": {
                    "POST /api/sightings": "Log a bird sighting (catch!)",
                    "GET /api/sightings/user/<user_id>": "User's sighting history",
                    "GET /api/sightings/<id>": "Sighting details",
                },
                "birdex": {
                    "GET /api/birdex/<user_id>": "User's Birdex collection (filter: rarity, habitat, show=all|caught|uncaught)",
                    "GET /api/birdex/<user_id>/stats": "Collection stats by rarity/habitat/region",
                },
                "leaderboard": {
                    "GET /api/leaderboard": "Global rankings (sort: xp, level, total_sightings, streak)",
                    "GET /api/leaderboard/user/<user_id>": "User's rank",
                },
            },
        })

    with app.app_context():
        db.create_all()
        seed_database()

    return app


def seed_database():
    """Populate the database with birds and achievements if empty."""
    if Bird.query.first() is not None:
        return

    for bird_data in BIRDS:
        bird = Bird(
            common_name=bird_data["common_name"],
            scientific_name=bird_data["scientific_name"],
            rarity=bird_data["rarity"],
            family=bird_data.get("family"),
            habitat=bird_data.get("habitat"),
            region=bird_data.get("region"),
            description=bird_data.get("description"),
            xp_value=RARITY_XP.get(bird_data["rarity"], 10),
        )
        db.session.add(bird)

    for ach_data in ACHIEVEMENTS:
        achievement = Achievement(
            name=ach_data["name"],
            description=ach_data["description"],
            icon=ach_data.get("icon"),
            category=ach_data["category"],
            requirement_type=ach_data["requirement_type"],
            requirement_value=ach_data["requirement_value"],
        )
        db.session.add(achievement)

    db.session.commit()
    print(f"Seeded {len(BIRDS)} birds and {len(ACHIEVEMENTS)} achievements.")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
