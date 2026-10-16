"""SQLAlchemy engine, session, and base class."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    # SQLite needs check_same_thread=False for use in async context
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=False,
        future=True,
    )

    # Enable WAL mode + foreign keys for SQLite
    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Called on app startup."""
    # Import models so they register with Base.metadata
    from app.models import entity, event as event_model, file, issue, project, revision  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.services.events import ensure_event_table

    ensure_event_table(engine)
