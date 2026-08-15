import hmac
import os
import secrets
import warnings

from flask import Flask, jsonify, request, session
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

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
                    "PUT /api/profile/timezone": "Set your timezone (drives daily rollover)",
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
                "challenges": {
                    "GET /api/challenges": "Today's daily quests",
                },
                "encounter": {
                    "GET /api/encounter": "A weighted random bird encounter",
                    "GET /api/encounter/batch": "Several encounters at once",
                },
                "birdex": {
                    "GET /api/birdex/<user_id>": "User's Birdex collection (filter: rarity, habitat, show=all|caught|uncaught)",
                    "GET /api/birdex/<user_id>/stats": "Collection stats by rarity/habitat/region",
                },
                "leaderboard": {
                    "GET /api/leaderboard": "Global rankings (sort: xp, level, total_sightings, unique_species, streak)",
                    "GET /api/leaderboard/user/<user_id>": "User's rank",
                },
            },
        })

    _register_csrf(app)
    _register_error_handlers(app)

    with app.app_context():
        db.create_all()
        seed_database()

    return app


CSRF_METHODS = ("POST", "PUT", "PATCH", "DELETE")
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def _register_csrf(app):
    """Double-submit CSRF protection for authenticated, state-changing API calls.

    The token lives in the signed session and is mirrored into a JS-readable
    cookie. Requests without a session are exempt: there is no authenticated
    context to abuse, and login/register must work for a fresh client.
    """

    @app.before_request
    def _csrf_protect():
        if request.method not in CSRF_METHODS:
            return None
        if not request.path.startswith("/api/"):
            return None
        if session.get("user_id") is None:
            return None
        expected = session.get("csrf_token")
        provided = request.headers.get(CSRF_HEADER, "")
        if not expected or not hmac.compare_digest(expected, provided):
            return jsonify({"error": "Invalid or missing CSRF token"}), 403
        return None

    @app.after_request
    def _issue_csrf_cookie(response):
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        if request.cookies.get(CSRF_COOKIE) != token:
            response.set_cookie(
                CSRF_COOKIE,
                token,
                httponly=False,  # the frontend must read this to echo it back
                samesite="Lax",
                secure=app.config.get("SESSION_COOKIE_SECURE", False),
            )
        return response


def _register_error_handlers(app):
    """Return JSON (not Werkzeug HTML) for errors on API routes."""

    @app.errorhandler(HTTPException)
    def _handle_http_exception(err):
        if not request.path.startswith("/api/"):
            return err
        return jsonify({"error": err.description, "status": err.code}), err.code

    @app.errorhandler(Exception)
    def _handle_unexpected(err):
        app.logger.exception("Unhandled error on %s", request.path)
        db.session.rollback()
        if not request.path.startswith("/api/"):
            raise err
        return jsonify({"error": "Internal server error", "status": 500}), 500


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

    try:
        db.session.commit()
    except IntegrityError:
        # Another worker seeded first during a concurrent boot; theirs stands.
        db.session.rollback()
        return
    print(f"Seeded {len(BIRDS)} birds and {len(ACHIEVEMENTS)} achievements.")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
