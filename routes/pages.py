from flask import Blueprint, render_template, session, redirect, url_for
from models import db, User, Bird, Sighting, Achievement, LEVEL_THRESHOLDS
from routes.auth import login_required

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("pages.dashboard"))
    return render_template("landing.html")


@pages_bp.route("/dashboard")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    recent_sightings = user.sightings.order_by(Sighting.spotted_at.desc()).limit(5).all()
    next_level_xp = LEVEL_THRESHOLDS[user.level] if user.level < len(LEVEL_THRESHOLDS) else None
    prev_level_xp = LEVEL_THRESHOLDS[user.level - 1] if user.level > 0 else 0
    return render_template(
        "dashboard.html",
        user=user,
        sightings=recent_sightings,
        next_level_xp=next_level_xp,
        prev_level_xp=prev_level_xp,
        total_birds=Bird.query.count(),
    )


@pages_bp.route("/catalog")
def catalog():
    birds = Bird.query.order_by(Bird.rarity, Bird.common_name).all()
    return render_template("catalog.html", birds=birds)


@pages_bp.route("/catch")
@login_required
def catch():
    birds = Bird.query.order_by(Bird.common_name).all()
    return render_template("log_sighting.html", birds=birds)


@pages_bp.route("/birdex")
@login_required
def birdex():
    user = User.query.get(session["user_id"])
    caught_ids = {b.id for b in user.caught_birds}
    all_birds = Bird.query.order_by(Bird.common_name).all()

    entries = []
    for bird in all_birds:
        is_caught = bird.id in caught_ids
        entry = {"bird": bird, "caught": is_caught}
        if is_caught:
            entry["times_spotted"] = Sighting.query.filter_by(
                user_id=user.id, bird_id=bird.id
            ).count()
        entries.append(entry)

    total = len(all_birds)
    caught_count = len(caught_ids)
    completion_pct = round(caught_count / total * 100, 1) if total > 0 else 0

    return render_template(
        "birdex.html",
        entries=entries,
        total=total,
        caught_count=caught_count,
        completion_pct=completion_pct,
    )


@pages_bp.route("/achievements")
@login_required
def achievements():
    user = User.query.get(session["user_id"])
    earned_ids = {a.id for a in user.achievements}
    all_achievements = Achievement.query.all()

    entries = []
    for ach in all_achievements:
        entries.append({"achievement": ach, "earned": ach.id in earned_ids})

    return render_template("achievements.html", entries=entries, user=user)


@pages_bp.route("/leaderboard")
def leaderboard():
    users = User.query.order_by(User.xp.desc()).limit(50).all()
    return render_template("leaderboard.html", users=users)
