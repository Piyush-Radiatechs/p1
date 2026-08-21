"""Database engine and session helpers.

Local default is SQLite (./data/app.db). For Streamlit Cloud, set DATABASE_URL
to a free hosted Postgres URL (Neon or Supabase).
"""

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.config import get_settings
from app.db.models import Base, Search, SearchResult, User
from app.exceptions import DatabaseError

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw_path = url.removeprefix("sqlite:///")
    if raw_path.startswith(":memory:"):
        return
    path = Path(raw_path)
    if path.parent and str(path.parent) not in {".", ""}:
        path.parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    url = get_settings().sqlalchemy_database_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        else:
            _ensure_sqlite_dir(url)
    else:
        # Neon pooler + idle compute: avoid SQLAlchemy pooling and drop stale sockets.
        kwargs.update(
            {
                "poolclass": NullPool,
                "pool_pre_ping": True,
                "connect_args": {"connect_timeout": 30},
            }
        )

    try:
        _engine = create_engine(url, **kwargs)
    except Exception as exc:
        raise DatabaseError(f"Could not connect to the database: {exc}") from exc

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _engine


def _session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    """Create tables if they do not exist.

    Neon free-tier compute sleeps when idle; the first SSL connection often
    drops, so a few retries are needed while the instance wakes up.
    """
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            Base.metadata.create_all(get_engine())
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning("Database init attempt %s failed: %s", attempt, exc)
            reset_engine()
            if attempt < 3:
                time.sleep(1.5 * attempt)
    raise DatabaseError(
        "Could not connect to Neon. Wait a few seconds for the database to wake up, "
        "then refresh the page. Confirm DATABASE_URL uses sslmode=require."
    ) from last_error


def reset_engine() -> None:
    """Dispose the engine so tests can switch DATABASE_URL."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "Base",
    "Search",
    "SearchResult",
    "User",
    "get_engine",
    "init_db",
    "reset_engine",
    "session_scope",
]
