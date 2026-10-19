"""Synchronous SQLAlchemy engine and FastAPI connection dependency."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared application engine, creating it on first use.

    Importing this module does not read ``DATABASE_URL`` or open a
    connection. The engine is created from ``settings.database_url``
    when a connection is first requested.
    """
    global _engine
    if _engine is None:
        from app.core.config import settings

        _engine = create_engine(settings.database_url)
    return _engine


def get_connection() -> Iterator[Connection]:
    """Yield a SQLAlchemy connection and close it afterward.

    Connections are opened when this dependency is used, not at import
    time. The caller owns any transaction.
    """
    connection = get_engine().connect()
    try:
        yield connection
    finally:
        connection.close()
