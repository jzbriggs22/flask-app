import os
from flask import Flask, jsonify
from models import db, Bird, Achievement, RARITY_XP
from seed_data import BIRDS, ACHIEVEMENTS
from routes import (
    auth_bp, birds_bp, sightings_bp, birdex_bp, leaderboard_bp,
    challenges_bp, encounter_bp, pages_bp,
)


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///birding.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

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


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
