"""Unit tests for the persistence layer itself (engine/URL resolution).

These cover the branches the route tests never hit, because those run against
an in-memory database and so skip the file-path and env-resolution code.
"""

from sqlalchemy import text

import persistence.db as db


def test_default_database_url_uses_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host/db")
    assert db.default_database_url() == "postgresql+psycopg://u:p@host/db"


def test_default_database_url_defaults_to_sqlite_file(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = db.default_database_url()
    assert url.startswith("sqlite:///")
    assert url.endswith("storable.db")


def test_make_engine_creates_missing_parent_dir(tmp_path):
    target = tmp_path / "nested" / "dir" / "storable.db"
    engine = db.make_engine(f"sqlite:///{target}")
    assert target.parent.exists()  # make_engine mkdir'd it
    with engine.connect() as conn:
        assert conn.execute(text("select 1")).scalar() == 1


def test_make_engine_memory_shares_one_connection():
    # StaticPool means data written via one session is visible to the next,
    # which is exactly why in-memory works for the test suite.
    engine = db.make_engine("sqlite:///:memory:")
    db.init_db(engine)
    Session = db.make_session_factory(engine)

    from models.models import Marina

    with Session() as s:
        s.add(Marina(name="Isolated"))
        s.commit()
    with Session() as s:
        assert s.query(Marina).count() == 1
