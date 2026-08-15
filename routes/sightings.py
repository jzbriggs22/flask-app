from datetime import datetime, time, timedelta, timezone

from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import IntegrityError

from models import (
    db, User, Bird, Sighting, RARITY_XP, MAX_STREAK_BONUS, REPEAT_XP_FACTOR,
)
from routes.auth import login_required, current_user

sightings_bp = Blueprint("sightings", __name__)

MAX_PER_PAGE = 100


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


def _local_day_bounds_utc(user):
    """The user's current local calendar day, expressed as naive-UTC bounds.

    spotted_at is persisted as naive UTC, so the local-midnight boundaries are
    converted to UTC before they are used in a query.
    """
    tz = user.tzinfo()
    start_local = datetime.combine(user.today(), time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _already_logged_today(user, bird):
    """True if the user already logged this species during their local day."""
    start_utc, end_utc = _local_day_bounds_utc(user)
    return db.session.query(
        Sighting.query.filter(
            Sighting.user_id == user.id,
            Sighting.bird_id == bird.id,
            Sighting.spotted_at >= start_utc,
            Sighting.spotted_at < end_utc,
        ).exists()
    ).scalar()


@sightings_bp.route("/sightings", methods=["POST"])
@login_required
def log_sighting():
    """
    Log a bird sighting -- the core 'catch' mechanic.
    Awards XP, updates streaks, checks for new species, and triggers achievements.

    The acting user is always taken from the authenticated session; any user_id
    in the request body is ignored so one account cannot act as another.
    """
    data = request.get_json(silent=True) or {}

    user = current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    bird_id = data.get("bird_id")
    if not isinstance(bird_id, int):
        return jsonify({"error": "bird_id is required and must be an integer"}), 400

    lat = data.get("latitude")
    lng = data.get("longitude")
    if lat is not None and not isinstance(lat, (int, float)):
        return jsonify({"error": "latitude must be a number"}), 400
    if lng is not None and not isinstance(lng, (int, float)):
        return jsonify({"error": "longitude must be a number"}), 400

    bird = Bird.query.get(bird_id)
    if not bird:
        return jsonify({"error": "Bird not found"}), 404

    # Check if this is a new species for the user
    is_new = bird not in user.caught_birds

    # Update the streak first so the bonus reflects today's (post-update) streak.
    old_level = user.level
    user.update_streak()

    # Has this species already been logged today? Repeats still count toward
    # quests, but earn reduced XP so the leaderboard is not a clicking contest.
    is_repeat_today = _already_logged_today(user, bird)

    # Calculate XP. The bird's own xp_value is authoritative (it is what the
    # catalog and encounter screens advertise); RARITY_XP is only a fallback.
    base_xp = bird.xp_value or RARITY_XP.get(bird.rarity, 10)
    bonus_xp = base_xp if is_new else 0  # Double XP for new species
    streak_bonus = 0 if is_repeat_today else min(user.streak_days * 2, MAX_STREAK_BONUS)
    if is_repeat_today:
        base_xp = max(1, int(base_xp * REPEAT_XP_FACTOR))
    total_xp = base_xp + bonus_xp + streak_bonus

    # Create sighting record
    sighting = Sighting(
        user_id=user.id,
        bird_id=bird.id,
        latitude=lat,
        longitude=lng,
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
    user.add_xp(total_xp)

    # Apply daily-challenge rewards BEFORE computing level-up and achievements so
    # that a level (or level-based achievement) crossed by challenge XP is reported.
    from routes.challenges import update_challenges_for_sighting
    completed_challenges = update_challenges_for_sighting(user, bird, is_new)

    new_level = user.level
    leveled_up = new_level > old_level

    # Check achievements after all XP (sighting + challenge) has been applied.
    newly_earned = check_achievements(user)

    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent request logged this same new species first; the whole
        # transaction rolls back, so report a conflict instead of a 500.
        db.session.rollback()
        return jsonify({
            "error": "That sighting conflicted with a simultaneous request. Please retry."
        }), 409

    response = {
        "sighting": sighting.to_dict(),
        "xp_breakdown": {
            "base_xp": base_xp,
            "new_species_bonus": bonus_xp,
            "streak_bonus": streak_bonus,
            "repeat_sighting": is_repeat_today,
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
@login_required
def get_user_sightings(user_id):
    """Get all sightings for the authenticated user, most recent first.

    A user may only read their own sightings; the response includes precise GPS
    coordinates, so cross-user access is forbidden.
    """
    if session.get("user_id") != user_id:
        return jsonify({"error": "Forbidden"}), 403

    user = User.query.get_or_404(user_id)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = max(1, min(per_page, MAX_PER_PAGE))

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
@login_required
def get_sighting(sighting_id):
    """Get details for a specific sighting (owner only, since it exposes GPS)."""
    sighting = Sighting.query.get_or_404(sighting_id)
    if sighting.user_id != session.get("user_id"):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(sighting.to_dict()), 200
