"""Database configuration and session management utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings

load_dotenv()

Base = declarative_base()
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None

DEFAULT_SQLITE_PATH = Path("instance") / "app.db"


def _build_engine(database_url: str) -> Engine:
    kwargs = {"future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **kwargs)


def init_engine(database_url: Optional[str] = None) -> Engine:
    """Initialise the global engine and session factory."""

    global _engine, _SessionLocal

    if database_url is None:
        settings = get_settings()
        database_url = settings.database_url or os.getenv("DATABASE_URL")
        if not database_url:
            instance_dir = DEFAULT_SQLITE_PATH.parent
            instance_dir.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{DEFAULT_SQLITE_PATH}"  # default local DB

    _engine = _build_engine(database_url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine() -> Engine:
    """Return the active SQLAlchemy engine, initialising if necessary."""

    global _engine
    if _engine is None:
        _engine = init_engine()
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Provide a transactional session for request handling."""

    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    """Create database tables based on the declarative metadata."""

    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_session_factory() -> sessionmaker:
    """Expose the configured session factory (useful for CLI utilities)."""

    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal
