from flask import Blueprint, request, jsonify
from models import db, User, Bird, Sighting

birdex_bp = Blueprint("birdex", __name__)


@birdex_bp.route("/birdex/<int:user_id>", methods=["GET"])
def get_birdex(user_id):
    """
    Get a user's Birdex -- their personal collection of spotted species.
    Similar to a Pokedex, shows which birds they've found and which remain undiscovered.
    """
    user = User.query.get_or_404(user_id)
    caught_ids = {b.id for b in user.caught_birds}

    # Optional filters
    rarity = request.args.get("rarity")
    habitat = request.args.get("habitat")
    region = request.args.get("region")
    show = request.args.get("show", "all")  # all, caught, uncaught

    query = Bird.query
    if rarity:
        query = query.filter_by(rarity=rarity)
    if habitat:
        query = query.filter_by(habitat=habitat)
    if region:
        query = query.filter_by(region=region)

    all_birds = query.order_by(Bird.common_name).all()

    birdex_entries = []
    for bird in all_birds:
        is_caught = bird.id in caught_ids

        if show == "caught" and not is_caught:
            continue
        if show == "uncaught" and is_caught:
            continue

        entry = {
            "bird_id": bird.id,
            "caught": is_caught,
        }
        if is_caught:
            # Show full details for caught birds
            entry.update(bird.to_dict())
            # Add sighting stats
            sighting_count = Sighting.query.filter_by(
                user_id=user.id, bird_id=bird.id
            ).count()
            first_sighting = Sighting.query.filter_by(
                user_id=user.id, bird_id=bird.id
            ).order_by(Sighting.spotted_at.asc()).first()
            entry["times_spotted"] = sighting_count
            entry["first_spotted"] = first_sighting.spotted_at.isoformat() if first_sighting else None
        else:
            # Mystery entry -- just show silhouette info
            entry["common_name"] = "???"
            entry["rarity"] = bird.rarity
            entry["habitat"] = bird.habitat
            entry["region"] = bird.region

        birdex_entries.append(entry)

    total = len(all_birds)
    caught_count = sum(1 for e in birdex_entries if e["caught"])

    return jsonify({
        "user_id": user.id,
        "username": user.username,
        "total_species": total,
        "caught_species": caught_count,
        "completion_pct": round(caught_count / total * 100, 1) if total > 0 else 0,
        "entries": birdex_entries,
    }), 200


@birdex_bp.route("/birdex/<int:user_id>/stats", methods=["GET"])
def get_birdex_stats(user_id):
    """Get collection statistics broken down by rarity, habitat, region."""
    user = User.query.get_or_404(user_id)
    caught_ids = {b.id for b in user.caught_birds}

    all_birds = Bird.query.all()

    # Build stats by category
    def build_breakdown(attr):
        breakdown = {}
        for bird in all_birds:
            key = getattr(bird, attr) or "unknown"
            if key not in breakdown:
                breakdown[key] = {"total": 0, "caught": 0}
            breakdown[key]["total"] += 1
            if bird.id in caught_ids:
                breakdown[key]["caught"] += 1
        return breakdown

    return jsonify({
        "by_rarity": build_breakdown("rarity"),
        "by_habitat": build_breakdown("habitat"),
        "by_region": build_breakdown("region"),
    }), 200
