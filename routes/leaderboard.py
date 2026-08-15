from flask import Blueprint, request, jsonify

from models import db, User, user_sightings

leaderboard_bp = Blueprint("leaderboard", __name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
VALID_SORTS = ("xp", "level", "total_sightings", "unique_species", "streak")


@leaderboard_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    Get the global leaderboard.
    Supports sorting by: xp (default), level, total_sightings, unique_species, streak.
    An unrecognized sort is rejected rather than silently falling back to xp.
    """
    sort_by = request.args.get("sort", "xp")
    if sort_by not in VALID_SORTS:
        return jsonify({
            "error": f"Invalid sort '{sort_by}'. Valid options: {', '.join(VALID_SORTS)}"
        }), 400

    limit = request.args.get("limit", DEFAULT_LIMIT, type=int) or DEFAULT_LIMIT
    limit = max(1, min(limit, MAX_LIMIT))

    if sort_by == "unique_species":
        # Rank by distinct caught species, counted in SQL.
        species_count = db.func.count(user_sightings.c.bird_id)
        rows = (
            db.session.query(User, species_count.label("species"))
            .outerjoin(user_sightings, user_sightings.c.user_id == User.id)
            .group_by(User.id)
            .order_by(species_count.desc(), User.xp.desc())
            .limit(limit)
            .all()
        )
        users = [row[0] for row in rows]
    else:
        order = {
            "xp": (User.xp.desc(),),
            "level": (User.level.desc(), User.xp.desc()),
            "total_sightings": (User.total_sightings.desc(),),
            "streak": (User.streak_days.desc(),),
        }[sort_by]
        users = User.query.order_by(*order).limit(limit).all()

    leaderboard = []
    for rank, user in enumerate(users, 1):
        entry = user.to_dict()
        entry["rank"] = rank
        leaderboard.append(entry)

    return jsonify({
        "sort_by": sort_by,
        "limit": limit,
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
