"""Shared SQLite database fixture for auth and history tests."""

import pytest

from app.config import get_settings
from app.db import init_db, reset_engine


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.resolve().as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()
    get_settings.cache_clear()
