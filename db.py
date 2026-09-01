"""Database layer: engine, session, and schema bootstrap.

The engine is chosen by the DATABASE_URL environment variable and falls back
to a local SQLite file (storable.db) sitting next to this module. Switching to
PostgreSQL later is a matter of setting, e.g.:

    DATABASE_URL=postgresql+psycopg://user:pass@localhost/storable

...with no changes to the models or route code.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default: a SQLite file living beside this project.
_DEFAULT_SQLITE_PATH = Path(__file__).with_name("storable.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

# check_same_thread is a SQLite-only concern (Flask's dev server is threaded).
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""


def init_db():
    """Create any tables that don't yet exist. Safe to call on every startup."""
    # Import models so they register on Base.metadata before create_all runs.
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)