from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
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

MAX_STREAK_BONUS = 50
# Repeat sightings of the same species on the same day earn this fraction of
# base XP (and no streak bonus), so the leaderboard measures birding, not clicks.
REPEAT_XP_FACTOR = 0.25

DEFAULT_TIMEZONE = "UTC"

# ---------- Achievement icons ----------
# Single source of truth for icon key -> emoji. Serialized through
# Achievement.to_dict() as `icon_emoji` so templates and JS never duplicate it.
ICON_EMOJI = {
    "egg": "\U0001F95A",
    "eyes": "\U0001F440",
    "binoculars": "\U0001F52D",
    "star": "⭐",
    "crown": "\U0001F451",
    "seedling": "\U0001F331",
    "herb": "\U0001F33F",
    "book": "\U0001F4D6",
    "mortar_board": "\U0001F393",
    "fire": "\U0001F525",
    "mag": "\U0001F50D",
    "gem": "\U0001F48E",
    "dizzy": "\U0001F4AB",
    "trophy": "\U0001F3C6",
    "bird": "\U0001F426",
    "eagle": "\U0001F985",
    "rocket": "\U0001F680",
    "100": "\U0001F4AF",
}
DEFAULT_ICON_EMOJI = "\U0001F3C5"


def icon_to_emoji(icon_name):
    """Map a stored icon key to its display emoji."""
    return ICON_EMOJI.get(icon_name, DEFAULT_ICON_EMOJI)


# ---------- Timezone helpers ----------

def is_valid_timezone(tzname):
    return isinstance(tzname, str) and tzname in available_timezones()


def local_today(tzname=None):
    """Today's calendar date in the given IANA timezone (falling back to UTC).

    Daily mechanics (streaks, quests) roll over at the user's local midnight
    rather than UTC midnight, which would otherwise land mid-afternoon for
    much of the target audience.
    """
    try:
        tz = ZoneInfo(tzname) if tzname else ZoneInfo(DEFAULT_TIMEZONE)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce foreign keys on SQLite (off by default), so ON DELETE works."""
    module = type(dbapi_connection).__module__ or ""
    if "sqlite" in module:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------- Association Tables ----------

# Birds a user has spotted (their Birdex)
user_sightings = db.Table(
    "user_sightings",
    db.Column("user_id", db.Integer,
              db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("bird_id", db.Integer,
              db.ForeignKey("bird.id", ondelete="CASCADE"), primary_key=True),
)

# Achievements a user has earned
user_achievements = db.Table(
    "user_achievements",
    db.Column("user_id", db.Integer,
              db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("achievement_id", db.Integer,
              db.ForeignKey("achievement.id", ondelete="CASCADE"), primary_key=True),
    db.Column("earned_at", db.DateTime, default=lambda: datetime.now(timezone.utc)),
)


# ---------- Models ----------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # IANA timezone name; drives the local-midnight boundary for daily mechanics.
    timezone = db.Column(db.String(64), nullable=False, default=DEFAULT_TIMEZONE)

    # Gamification
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    total_sightings = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_sighting_date = db.Column(db.Date, nullable=True)

    # Relationships. Deleting a user removes their sightings and challenges
    # rather than orphaning rows or violating the NOT NULL foreign keys.
    sightings = db.relationship(
        "Sighting", backref="user", lazy="dynamic",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    caught_birds = db.relationship("Bird", secondary=user_sightings, backref="caught_by")
    achievements = db.relationship("Achievement", secondary=user_achievements, backref="earned_by")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def tzinfo(self):
        """This user's tzinfo object, falling back to UTC if unset/invalid."""
        try:
            return ZoneInfo(self.timezone or DEFAULT_TIMEZONE)
        except Exception:
            return ZoneInfo(DEFAULT_TIMEZONE)

    def today(self):
        """Today's date in this user's timezone."""
        return local_today(self.timezone)

    def add_xp(self, amount):
        # Column defaults only apply at flush time, so a not-yet-persisted user
        # still has xp=None; coerce so this is safe on transient instances too.
        self.xp = (self.xp or 0) + amount
        # Recalculate level
        for i, threshold in enumerate(LEVEL_THRESHOLDS):
            if self.xp < threshold:
                self.level = i
                return self.level
        self.level = len(LEVEL_THRESHOLDS)
        return self.level

    def update_streak(self):
        today = self.today()
        if self.last_sighting_date is None:
            self.streak_days = 1
        elif self.streak_days is None:
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
            "unique_species": self.unique_species_count,
            "streak_days": self.streak_days,
            "achievements_count": self.achievements_count,
            "timezone": self.timezone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    # Counts are looked up with a COUNT query rather than by loading and
    # len()-ing the full collections (which hydrated every related row).
    @property
    def unique_species_count(self):
        if "caught_birds" in self.__dict__:
            return len(self.__dict__["caught_birds"])
        return db.session.query(db.func.count()).select_from(user_sightings).filter(
            user_sightings.c.user_id == self.id
        ).scalar() or 0

    @property
    def achievements_count(self):
        if "achievements" in self.__dict__:
            return len(self.__dict__["achievements"])
        return db.session.query(db.func.count()).select_from(user_achievements).filter(
            user_achievements.c.user_id == self.id
        ).scalar() or 0


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

    __table_args__ = (
        db.UniqueConstraint("scientific_name", name="uq_bird_scientific_name"),
        db.Index("ix_bird_rarity", "rarity"),
        db.Index("ix_bird_habitat", "habitat"),
    )

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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    bird_id = db.Column(db.Integer, db.ForeignKey("bird.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_name = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    spotted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    challenge_type = db.Column(db.String(50), nullable=False)  # spot_count, spot_rarity, spot_habitat, spot_new
    target_value = db.Column(db.String(100), nullable=False)  # e.g. "3" for count, "rare" for rarity
    target_count = db.Column(db.Integer, nullable=False, default=1)
    current_count = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    xp_reward = db.Column(db.Integer, nullable=False, default=50)
    description = db.Column(db.String(200), nullable=False)

    user_rel = db.relationship(
        "User",
        backref=db.backref("daily_challenges", lazy="dynamic",
                           cascade="all, delete-orphan", passive_deletes=True),
    )

    # One row per user per day per challenge type: makes the check-then-insert
    # in generate_daily_challenges safe under concurrent workers.
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", "challenge_type",
                            name="uq_daily_challenge_user_date_type"),
    )

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
    icon = db.Column(db.String(50), nullable=True)  # icon key; see ICON_EMOJI
    category = db.Column(db.String(50), nullable=False)  # collection, streak, exploration, mastery
    requirement_type = db.Column(db.String(50), nullable=False)  # total_sightings, unique_species, streak, etc.
    requirement_value = db.Column(db.Integer, nullable=False)  # threshold to earn

    @property
    def icon_emoji(self):
        return icon_to_emoji(self.icon)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "icon_emoji": self.icon_emoji,
            "category": self.category,
            "requirement_type": self.requirement_type,
            "requirement_value": self.requirement_value,
        }
