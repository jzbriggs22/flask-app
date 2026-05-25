from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------- XP & Level Config ----------
# XP required to reach each level (cumulative thresholds)
LEVEL_THRESHOLDS = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5500,
                    7500, 10000, 13000, 17000, 22000, 28000, 35000, 43000,
                    52000, 62500]  # Levels 1-20

RARITY_XP = {
    "common": 10,
    "uncommon": 25,
    "rare": 50,
    "epic": 100,
    "legendary": 250,
}

# ---------- Association Tables ----------

# Birds a user has spotted (their Birdex)
user_sightings = db.Table(
    "user_sightings",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("bird_id", db.Integer, db.ForeignKey("bird.id"), primary_key=True),
)

# Achievements a user has earned
user_achievements = db.Table(
    "user_achievements",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("achievement_id", db.Integer, db.ForeignKey("achievement.id"), primary_key=True),
    db.Column("earned_at", db.DateTime, default=lambda: datetime.now(timezone.utc)),
)


# ---------- Models ----------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Gamification
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    total_sightings = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_sighting_date = db.Column(db.Date, nullable=True)

    # Relationships
    sightings = db.relationship("Sighting", backref="user", lazy="dynamic")
    caught_birds = db.relationship("Bird", secondary=user_sightings, backref="caught_by")
    achievements = db.relationship("Achievement", secondary=user_achievements, backref="earned_by")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def add_xp(self, amount):
        self.xp += amount
        # Recalculate level
        for i, threshold in enumerate(LEVEL_THRESHOLDS):
            if self.xp < threshold:
                self.level = i
                return self.level
        self.level = len(LEVEL_THRESHOLDS)
        return self.level

    def update_streak(self):
        today = datetime.now(timezone.utc).date()
        if self.last_sighting_date is None:
            self.streak_days = 1
        elif (today - self.last_sighting_date).days == 1:
            self.streak_days += 1
        elif (today - self.last_sighting_date).days > 1:
            self.streak_days = 1
        # Same day = no change
        self.last_sighting_date = today

    def to_dict(self):
        next_level_xp = LEVEL_THRESHOLDS[self.level] if self.level < len(LEVEL_THRESHOLDS) else None
        return {
            "id": self.id,
            "username": self.username,
            "xp": self.xp,
            "level": self.level,
            "next_level_xp": next_level_xp,
            "total_sightings": self.total_sightings,
            "unique_species": len(self.caught_birds),
            "streak_days": self.streak_days,
            "achievements_count": len(self.achievements),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Bird(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    common_name = db.Column(db.String(120), nullable=False)
    scientific_name = db.Column(db.String(120), nullable=False)
    rarity = db.Column(db.String(20), nullable=False, default="common")  # common/uncommon/rare/epic/legendary
    family = db.Column(db.String(100), nullable=True)
    habitat = db.Column(db.String(100), nullable=True)  # forest, wetland, urban, grassland, coastal, mountain
    region = db.Column(db.String(100), nullable=True)  # north_america, europe, asia, etc.
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    xp_value = db.Column(db.Integer, nullable=False, default=10)

    sightings = db.relationship("Sighting", backref="bird", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "common_name": self.common_name,
            "scientific_name": self.scientific_name,
            "rarity": self.rarity,
            "family": self.family,
            "habitat": self.habitat,
            "region": self.region,
            "description": self.description,
            "image_url": self.image_url,
            "xp_value": self.xp_value,
        }


class Sighting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bird_id = db.Column(db.Integer, db.ForeignKey("bird.id"), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_name = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    spotted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # XP earned for this sighting
    xp_earned = db.Column(db.Integer, default=0)
    # Was this a new species for the user?
    is_new_species = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "bird": self.bird.to_dict() if self.bird else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_name": self.location_name,
            "notes": self.notes,
            "photo_url": self.photo_url,
            "spotted_at": self.spotted_at.isoformat() if self.spotted_at else None,
            "xp_earned": self.xp_earned,
            "is_new_species": self.is_new_species,
        }


class DailyChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    challenge_type = db.Column(db.String(50), nullable=False)  # spot_count, spot_rarity, spot_habitat, spot_new
    target_value = db.Column(db.String(100), nullable=False)  # e.g. "3" for count, "rare" for rarity, "forest" for habitat
    target_count = db.Column(db.Integer, nullable=False, default=1)
    current_count = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    xp_reward = db.Column(db.Integer, nullable=False, default=50)
    description = db.Column(db.String(200), nullable=False)

    user_rel = db.relationship("User", backref=db.backref("daily_challenges", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "challenge_type": self.challenge_type,
            "description": self.description,
            "target_count": self.target_count,
            "current_count": self.current_count,
            "completed": self.completed,
            "xp_reward": self.xp_reward,
            "progress_pct": round(min(self.current_count / self.target_count * 100, 100), 1),
        }


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(300), nullable=False)
    icon = db.Column(db.String(50), nullable=True)  # emoji or icon name
    category = db.Column(db.String(50), nullable=False)  # collection, streak, exploration, mastery
    requirement_type = db.Column(db.String(50), nullable=False)  # total_sightings, unique_species, streak, rarity_catch, etc.
    requirement_value = db.Column(db.Integer, nullable=False)  # threshold to earn

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "requirement_type": self.requirement_type,
            "requirement_value": self.requirement_value,
        }
