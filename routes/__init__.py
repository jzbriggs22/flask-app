from routes.auth import auth_bp
from routes.birds import birds_bp
from routes.sightings import sightings_bp
from routes.birdex import birdex_bp
from routes.leaderboard import leaderboard_bp
from routes.challenges import challenges_bp
from routes.encounter import encounter_bp
from routes.pages import pages_bp

__all__ = [
    "auth_bp", "birds_bp", "sightings_bp", "birdex_bp", "leaderboard_bp",
    "challenges_bp", "encounter_bp", "pages_bp",
]
