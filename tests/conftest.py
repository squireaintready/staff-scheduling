"""Shared pytest fixtures.

The database module resolves its SQLite path from the module-level
``DATABASE_PATH`` constant at call time, so each test can be pointed at an
isolated temporary database by patching that constant and re-initializing the
schema. This keeps tests hermetic — no shared state, no real ``scheduling.db``.
"""


import pytest

import database as db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Provide the ``database`` module backed by a fresh, empty SQLite file."""
    db_file = tmp_path / "test_scheduling.db"
    monkeypatch.setattr(db, "DATABASE_PATH", str(db_file))
    db.init_database()
    yield db
    # tmp_path is cleaned up by pytest automatically.
