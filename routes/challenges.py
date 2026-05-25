import random
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from models import db, User, Bird, Sighting, DailyChallenge

challenges_bp = Blueprint("challenges", __name__)

CHALLENGE_TEMPLATES = [
    {"type": "spot_count", "desc": "Spot {n} birds today", "min": 2, "max": 5, "xp": 50},
    {"type": "spot_rarity", "desc": "Spot an {val} bird", "rarities": ["uncommon", "rare"], "xp": 75},
    {"type": "spot_habitat", "desc": "Spot a bird from the {val} habitat", "habitats": ["forest", "wetland", "coastal", "grassland", "mountain"], "xp": 60},
    {"type": "spot_new", "desc": "Discover a new species", "xp": 100},
]


def generate_daily_challenges(user):
    today = datetime.now(timezone.utc).date()
    existing = DailyChallenge.query.filter_by(user_id=user.id, date=today).all()
    if existing:
        return existing

    challenges = []
    templates = random.sample(CHALLENGE_TEMPLATES, k=3)

    for tmpl in templates:
        ch = DailyChallenge(user_id=user.id, date=today)
        ch.challenge_type = tmpl["type"]
        ch.xp_reward = tmpl["xp"]

        if tmpl["type"] == "spot_count":
            n = random.randint(tmpl["min"], tmpl["max"])
            ch.target_value = str(n)
            ch.target_count = n
            ch.description = tmpl["desc"].format(n=n)
        elif tmpl["type"] == "spot_rarity":
            val = random.choice(tmpl["rarities"])
            ch.target_value = val
            ch.target_count = 1
            ch.description = tmpl["desc"].format(val=val)
        elif tmpl["type"] == "spot_habitat":
            val = random.choice(tmpl["habitats"])
            ch.target_value = val
            ch.target_count = 1
            ch.description = tmpl["desc"].format(val=val)
        elif tmpl["type"] == "spot_new":
            ch.target_value = "new"
            ch.target_count = 1
            ch.description = tmpl["desc"]

        db.session.add(ch)
        challenges.append(ch)

    db.session.commit()
    return challenges


def update_challenges_for_sighting(user, bird, is_new_species):
    today = datetime.now(timezone.utc).date()
    challenges = DailyChallenge.query.filter_by(user_id=user.id, date=today, completed=False).all()
    newly_completed = []

    for ch in challenges:
        advanced = False
        if ch.challenge_type == "spot_count":
            advanced = True
        elif ch.challenge_type == "spot_rarity" and bird.rarity == ch.target_value:
            advanced = True
        elif ch.challenge_type == "spot_habitat" and bird.habitat == ch.target_value:
            advanced = True
        elif ch.challenge_type == "spot_new" and is_new_species:
            advanced = True

        if advanced:
            ch.current_count += 1
            if ch.current_count >= ch.target_count:
                ch.completed = True
                user.add_xp(ch.xp_reward)
                newly_completed.append(ch)

    return newly_completed


@challenges_bp.route("/challenges", methods=["GET"])
def get_challenges():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    challenges = generate_daily_challenges(user)
    return jsonify({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "challenges": [c.to_dict() for c in challenges],
    }), 200
