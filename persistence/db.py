"""Database layer: the ORM base, engine/session factories, and schema bootstrap.

The engine is built per-application (see ``main.create_app``) from a database
URL rather than at import time. That makes the datastore injectable: production
uses the local SQLite file sitting next to this module (persistence/storable.db);
tests inject an isolated in-memory database. Moving to PostgreSQL is just a
different URL, e.g. ``postgresql+psycopg://user:pass@host/db`` — no model or
route changes.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""


def default_database_url():
    """Resolve the database URL: ``DATABASE_URL`` if set, else the local SQLite file."""
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    path = Path(__file__).with_name("storable.db")  # persistence/storable.db
    return f"sqlite:///{path}"


def make_engine(database_url):
    """Create an Engine for ``database_url`` with SQLite-friendly defaults.

    In-memory SQLite uses a StaticPool so every session shares the single
    connection — otherwise each new connection would open its own empty
    database and never see the created tables. File-based SQLite gets its
    parent directory created on demand.
    """
    if ":memory:" in database_url:
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    if database_url.startswith("sqlite:///"):
        db_path = database_url[len("sqlite:///"):]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def make_session_factory(engine):
    """Build a Session factory bound to ``engine``."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine):
    """Create any tables that don't yet exist. Safe to call on every startup."""
    # Import models so they register on Base.metadata before create_all runs.
    import models.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
