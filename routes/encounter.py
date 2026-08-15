import random
from flask import Blueprint, request, jsonify, session

from models import User, Bird

encounter_bp = Blueprint("encounter", __name__)

RARITY_WEIGHTS = {
    "common": 50,
    "uncommon": 25,
    "rare": 15,
    "epic": 8,
    "legendary": 2,
}


@encounter_bp.route("/encounter", methods=["GET"])
def random_encounter():
    """
    Generate a random bird encounter based on weighted rarity.
    Optionally filter by habitat or region query params.
    Higher-level users have slightly better odds of rare encounters.
    """
    habitat = request.args.get("habitat")
    region = request.args.get("region")

    query = Bird.query
    if habitat:
        query = query.filter_by(habitat=habitat)
    if region:
        query = query.filter_by(region=region)

    birds = query.all()
    if not birds:
        return jsonify({"error": "No birds found for given filters"}), 404

    user_id = session.get("user_id")
    level_bonus = 0
    caught_ids = set()
    if user_id:
        user = User.query.get(user_id)
        if user:
            level_bonus = user.level
            caught_ids = {b.id for b in user.caught_birds}

    weights = []
    for bird in birds:
        base_weight = RARITY_WEIGHTS.get(bird.rarity, 10)
        # Higher levels slightly boost rare encounter odds
        if bird.rarity in ("rare", "epic", "legendary"):
            base_weight += level_bonus
        # Slight boost for uncaught birds to help collection
        if bird.id not in caught_ids:
            base_weight += 3
        weights.append(base_weight)

    chosen = random.choices(birds, weights=weights, k=1)[0]
    is_caught = chosen.id in caught_ids

    return jsonify({
        "encounter": chosen.to_dict(),
        "already_caught": is_caught,
        "message": f"A wild {chosen.common_name} appeared!" if not is_caught
                   else f"You spotted a {chosen.common_name} again!",
    }), 200


@encounter_bp.route("/encounter/batch", methods=["GET"])
def batch_encounter():
    """Generate multiple encounters at once (simulating a walk through an area)."""
    count = request.args.get("count", 3, type=int)
    count = min(count, 6)
    habitat = request.args.get("habitat")
    region = request.args.get("region")

    query = Bird.query
    if habitat:
        query = query.filter_by(habitat=habitat)
    if region:
        query = query.filter_by(region=region)

    birds = query.all()
    if not birds:
        return jsonify({"error": "No birds found for given filters"}), 404

    user_id = session.get("user_id")
    caught_ids = set()
    if user_id:
        user = User.query.get(user_id)
        if user:
            caught_ids = {b.id for b in user.caught_birds}

    weights = [RARITY_WEIGHTS.get(b.rarity, 10) for b in birds]
    chosen = random.choices(birds, weights=weights, k=count)
    # Deduplicate
    seen = set()
    unique = []
    for bird in chosen:
        if bird.id not in seen:
            seen.add(bird.id)
            unique.append(bird)

    encounters = []
    for bird in unique:
        encounters.append({
            "bird": bird.to_dict(),
            "already_caught": bird.id in caught_ids,
        })

    return jsonify({"encounters": encounters}), 200
