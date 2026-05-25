from flask import Blueprint, request, jsonify, session
from models import db, User, Bird, Sighting, RARITY_XP, user_sightings

sightings_bp = Blueprint("sightings", __name__)


def check_achievements(user):
    """Check and award any newly earned achievements. Returns list of newly earned."""
    from models import Achievement

    all_achievements = Achievement.query.all()
    earned_ids = {a.id for a in user.achievements}
    newly_earned = []

    for achievement in all_achievements:
        if achievement.id in earned_ids:
            continue

        earned = False
        req_type = achievement.requirement_type
        req_val = achievement.requirement_value

        if req_type == "total_sightings":
            earned = user.total_sightings >= req_val
        elif req_type == "unique_species":
            earned = len(user.caught_birds) >= req_val
        elif req_type == "streak":
            earned = user.streak_days >= req_val
        elif req_type == "level":
            earned = user.level >= req_val
        elif req_type.startswith("rarity_"):
            rarity = req_type.replace("rarity_", "")
            count = db.session.query(db.func.count(db.distinct(Sighting.bird_id))).join(
                Bird
            ).filter(
                Sighting.user_id == user.id,
                Bird.rarity == rarity,
            ).scalar()
            earned = count >= req_val

        if earned:
            user.achievements.append(achievement)
            newly_earned.append(achievement)

    return newly_earned


@sightings_bp.route("/sightings", methods=["POST"])
def log_sighting():
    """
    Log a bird sighting -- the core 'catch' mechanic.
    Awards XP, updates streaks, checks for new species, and triggers achievements.
    """
    data = request.get_json() or {}

    user_id = data.get("user_id") or session.get("user_id")
    if not user_id or "bird_id" not in data:
        return jsonify({"error": "bird_id is required (user_id from session or body)"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    bird = Bird.query.get(data["bird_id"])
    if not bird:
        return jsonify({"error": "Bird not found"}), 404

    # Check if this is a new species for the user
    is_new = bird not in user.caught_birds

    # Calculate XP
    base_xp = RARITY_XP.get(bird.rarity, 10)
    bonus_xp = base_xp if is_new else 0  # Double XP for new species
    streak_bonus = min(user.streak_days * 2, 50)  # Up to 50 bonus XP for streaks
    total_xp = base_xp + bonus_xp + streak_bonus

    # Create sighting record
    sighting = Sighting(
        user_id=user.id,
        bird_id=bird.id,
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        location_name=data.get("location_name"),
        notes=data.get("notes"),
        photo_url=data.get("photo_url"),
        xp_earned=total_xp,
        is_new_species=is_new,
    )
    db.session.add(sighting)

    # Update user stats
    if is_new:
        user.caught_birds.append(bird)
    user.total_sightings += 1
    old_level = user.level
    user.update_streak()
    new_level = user.add_xp(total_xp)

    leveled_up = new_level > old_level

    # Check achievements
    newly_earned = check_achievements(user)

    # Update daily challenges
    from routes.challenges import update_challenges_for_sighting
    completed_challenges = update_challenges_for_sighting(user, bird, is_new)

    db.session.commit()

    response = {
        "sighting": sighting.to_dict(),
        "xp_breakdown": {
            "base_xp": base_xp,
            "new_species_bonus": bonus_xp,
            "streak_bonus": streak_bonus,
            "total_xp": total_xp,
        },
        "is_new_species": is_new,
        "user_stats": user.to_dict(),
    }

    if leveled_up:
        response["level_up"] = {
            "old_level": old_level,
            "new_level": new_level,
            "message": f"Congratulations! You reached level {new_level}!",
        }

    if newly_earned:
        response["new_achievements"] = [a.to_dict() for a in newly_earned]

    if completed_challenges:
        response["completed_challenges"] = [c.to_dict() for c in completed_challenges]

    return jsonify(response), 201


@sightings_bp.route("/sightings/user/<int:user_id>", methods=["GET"])
def get_user_sightings(user_id):
    """Get all sightings for a user, most recent first."""
    user = User.query.get_or_404(user_id)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = user.sightings.order_by(
        Sighting.spotted_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "sightings": [s.to_dict() for s in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@sightings_bp.route("/sightings/<int:sighting_id>", methods=["GET"])
def get_sighting(sighting_id):
    """Get details for a specific sighting."""
    sighting = Sighting.query.get_or_404(sighting_id)
    return jsonify(sighting.to_dict()), 200
