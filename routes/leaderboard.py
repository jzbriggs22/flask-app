from flask import Blueprint, request, jsonify
from models import db, User

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    Get the global leaderboard.
    Supports sorting by: xp (default), level, total_sightings, unique_species, streak.
    """
    sort_by = request.args.get("sort", "xp")
    limit = request.args.get("limit", 20, type=int)

    if sort_by == "xp":
        users = User.query.order_by(User.xp.desc()).limit(limit).all()
    elif sort_by == "level":
        users = User.query.order_by(User.level.desc(), User.xp.desc()).limit(limit).all()
    elif sort_by == "total_sightings":
        users = User.query.order_by(User.total_sightings.desc()).limit(limit).all()
    elif sort_by == "streak":
        users = User.query.order_by(User.streak_days.desc()).limit(limit).all()
    else:
        users = User.query.order_by(User.xp.desc()).limit(limit).all()

    leaderboard = []
    for rank, user in enumerate(users, 1):
        entry = user.to_dict()
        entry["rank"] = rank
        leaderboard.append(entry)

    return jsonify({
        "sort_by": sort_by,
        "leaderboard": leaderboard,
    }), 200


@leaderboard_bp.route("/leaderboard/user/<int:user_id>", methods=["GET"])
def get_user_rank(user_id):
    """Get a specific user's rank on the leaderboard."""
    user = User.query.get_or_404(user_id)

    # Calculate rank by XP
    xp_rank = User.query.filter(User.xp > user.xp).count() + 1
    sighting_rank = User.query.filter(
        User.total_sightings > user.total_sightings
    ).count() + 1

    total_users = User.query.count()

    return jsonify({
        "user": user.to_dict(),
        "rankings": {
            "xp_rank": xp_rank,
            "sightings_rank": sighting_rank,
            "total_users": total_users,
        },
    }), 200
