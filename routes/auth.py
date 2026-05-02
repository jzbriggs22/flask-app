from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, url_for

from models import db, User

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.headers.get("Accept", "").startswith("application/json"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("pages.landing"))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ("username", "email", "password")):
        return jsonify({"error": "username, email, and password are required"}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["username"] = user.username

    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ("username", "password")):
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
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
