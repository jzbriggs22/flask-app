import random

from flask import Blueprint, jsonify
from sqlalchemy.exc import IntegrityError

from models import db, DailyChallenge
from routes.auth import login_required, current_user

challenges_bp = Blueprint("challenges", __name__)

CHALLENGE_TEMPLATES = [
    {"type": "spot_count", "desc": "Spot {n} birds today", "min": 2, "max": 5, "xp": 50},
    {"type": "spot_rarity", "desc": "Spot {article} {val} bird", "rarities": ["uncommon", "rare"], "xp": 75},
    {"type": "spot_habitat", "desc": "Spot a bird from the {val} habitat", "habitats": ["forest", "wetland", "coastal", "grassland", "mountain"], "xp": 60},
    {"type": "spot_new", "desc": "Discover a new species", "xp": 100},
]

CHALLENGES_PER_DAY = 3


def _article_for(word):
    """Return 'an' before a vowel sound, else 'a' (avoids 'Spot an rare bird')."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _build_challenge(user_id, today, tmpl):
    ch = DailyChallenge(user_id=user_id, date=today)
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
        ch.description = tmpl["desc"].format(article=_article_for(val), val=val)
    elif tmpl["type"] == "spot_habitat":
        val = random.choice(tmpl["habitats"])
        ch.target_value = val
        ch.target_count = 1
        ch.description = tmpl["desc"].format(val=val)
    elif tmpl["type"] == "spot_new":
        ch.target_value = "new"
        ch.target_count = 1
        ch.description = tmpl["desc"]

    return ch


def generate_daily_challenges(user):
    """Return today's challenges for a user, creating them on first access.

    The unique constraint on (user_id, date, challenge_type) makes this safe
    under concurrent workers: a racing request that loses the insert simply
    re-reads the winner's rows instead of creating a duplicate set.
    """
    today = user.today()
    existing = DailyChallenge.query.filter_by(user_id=user.id, date=today).all()
    if existing:
        return existing

    templates = random.sample(CHALLENGE_TEMPLATES, k=CHALLENGES_PER_DAY)
    for tmpl in templates:
        db.session.add(_build_challenge(user.id, today, tmpl))

    try:
        db.session.commit()
    except IntegrityError:
        # Another worker generated today's set first; use theirs.
        db.session.rollback()

    return DailyChallenge.query.filter_by(user_id=user.id, date=today).all()


def update_challenges_for_sighting(user, bird, is_new_species):
    today = user.today()
    challenges = DailyChallenge.query.filter_by(
        user_id=user.id, date=today, completed=False
    ).all()
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
@login_required
def get_challenges():
    user = current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    challenges = generate_daily_challenges(user)
    return jsonify({
        "date": user.today().isoformat(),
        "challenges": [c.to_dict() for c in challenges],
    }), 200
