from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, url_for

from models import db, User

auth_bp = Blueprint("auth", __name__)

USERNAME_MAX = 80
EMAIL_MAX = 120
PASSWORD_MIN = 6


def _wants_json():
    return (
        request.path.startswith("/api/")
        or request.is_json
        or request.headers.get("Accept", "").startswith("application/json")
    )


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if _wants_json():
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("pages.landing"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    """Return the logged-in User from the session, or None (clearing a stale session)."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = User.query.get(user_id)
    if user is None:
        # Session references a user that no longer exists (e.g. after a DB reset).
        session.clear()
    return user


def _clean_str(value):
    return value.strip() if isinstance(value, str) else None


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object with username, email, and password is required"}), 400

    username = _clean_str(data.get("username"))
    email = _clean_str(data.get("email"))
    password = data.get("password") if isinstance(data.get("password"), str) else None

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required and must be non-empty strings"}), 400
    if len(username) > USERNAME_MAX or len(email) > EMAIL_MAX:
        return jsonify({"error": "username or email exceeds the maximum length"}), 400
    if len(password) < PASSWORD_MIN:
        return jsonify({"error": f"password must be at least {PASSWORD_MIN} characters"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["username"] = user.username

    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object with username and password is required"}), 400

    username = _clean_str(data.get("username"))
    password = data.get("password") if isinstance(data.get("password"), str) else None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user.id
    session["username"] = user.username

    return jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "user_id": user.id,
    }), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.route("/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    user = User.query.get_or_404(user_id)
    profile = user.to_dict()
    profile["achievements"] = [a.to_dict() for a in user.achievements]
    return jsonify(profile), 200
