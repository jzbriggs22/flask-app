from flask import Blueprint, request, jsonify
from models import db, Bird

birds_bp = Blueprint("birds", __name__)


@birds_bp.route("/birds", methods=["GET"])
def list_birds():
    """List all birds with optional filters."""
    rarity = request.args.get("rarity")
    habitat = request.args.get("habitat")
    region = request.args.get("region")
    family = request.args.get("family")
    search = request.args.get("search")

    query = Bird.query

    if rarity:
        query = query.filter_by(rarity=rarity)
    if habitat:
        query = query.filter_by(habitat=habitat)
    if region:
        query = query.filter_by(region=region)
    if family:
        query = query.filter_by(family=family)
    if search:
        query = query.filter(
            db.or_(
                Bird.common_name.ilike(f"%{search}%"),
                Bird.scientific_name.ilike(f"%{search}%"),
            )
        )

    birds = query.order_by(Bird.common_name).all()
    return jsonify({
        "count": len(birds),
        "birds": [b.to_dict() for b in birds],
    }), 200


@birds_bp.route("/birds/<int:bird_id>", methods=["GET"])
def get_bird(bird_id):
    """Get details for a specific bird."""
    bird = Bird.query.get_or_404(bird_id)
    data = bird.to_dict()
    data["times_spotted"] = bird.sightings.count()
    return jsonify(data), 200


@birds_bp.route("/birds/rarities", methods=["GET"])
def get_rarities():
    """Get bird counts by rarity tier."""
    rarities = db.session.query(
        Bird.rarity, db.func.count(Bird.id)
    ).group_by(Bird.rarity).all()
    return jsonify({r: c for r, c in rarities}), 200


@birds_bp.route("/birds/habitats", methods=["GET"])
def get_habitats():
    """Get bird counts by habitat."""
    habitats = db.session.query(
        Bird.habitat, db.func.count(Bird.id)
    ).group_by(Bird.habitat).all()
    return jsonify({h: c for h, c in habitats}), 200


@birds_bp.route("/birds/regions", methods=["GET"])
def get_regions():
    """Get bird counts by region."""
    regions = db.session.query(
        Bird.region, db.func.count(Bird.id)
    ).group_by(Bird.region).all()
    return jsonify({r: c for r, c in regions}), 200
