"""Guarded database access for integration tests.

Integration tests must set TEST_DATABASE_URL. They never read
DATABASE_URL or app.core.config.settings. The application and Alembic
CLI continue to use DATABASE_URL unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
REQUIRED_TEST_DATABASE_NAME = "baseball_intelligence_test"
FORBIDDEN_DATABASE_NAMES = frozenset({"baseball_intelligence"})
ALEMBIC_TEST_DATABASE_GUARD_ENV = "ALEMBIC_TEST_DATABASE_GUARD"
ALEMBIC_TEST_DATABASE_GUARD_VALUE = "1"


class DatabaseConfigurationError(RuntimeError):
    """Raised when tests are not configured to use the test database."""


def get_test_database_url(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return TEST_DATABASE_URL after validating scheme and database name.

    ``DATABASE_URL`` is ignored. Missing, empty, non-PostgreSQL,
    development, or incorrectly named databases raise
    DatabaseConfigurationError. The URL is never included in error
    messages.
    """
    source = os.environ if environ is None else environ
    url_text = source.get(TEST_DATABASE_URL_ENV, "").strip()
    if not url_text:
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL is not set. Integration tests require a "
            "dedicated database named baseball_intelligence_test and do "
            "not use DATABASE_URL or the application .env file."
        )

    try:
        parsed = make_url(url_text)
    except ArgumentError:
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL is not a valid SQLAlchemy URL."
        ) from None
    if parsed.get_backend_name() != "postgresql":
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL must be a PostgreSQL SQLAlchemy URL."
        )
    database_name = parsed.database
    if not database_name:
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL must include a database name."
        )
    if database_name in FORBIDDEN_DATABASE_NAMES:
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL must not point at the development "
            f"database '{database_name}'. Use "
            f"{REQUIRED_TEST_DATABASE_NAME}."
        )
    if database_name != REQUIRED_TEST_DATABASE_NAME:
        raise DatabaseConfigurationError(
            "TEST_DATABASE_URL must use database "
            f"{REQUIRED_TEST_DATABASE_NAME}."
        )
    return url_text


def create_test_engine() -> Engine:
    """Create an engine for baseball_intelligence_test only."""
    return create_engine(get_test_database_url())


def alembic_test_database_guard_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return True only when the explicit Alembic test-guard flag is set."""
    source = os.environ if environ is None else environ
    return (
        source.get(ALEMBIC_TEST_DATABASE_GUARD_ENV, "").strip()
        == ALEMBIC_TEST_DATABASE_GUARD_VALUE
    )


def enforce_alembic_test_database_guard(
    connection,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Abort if the Alembic test guard is active on the wrong database.

    When the guard flag is unset, this is a no-op so the development
    Alembic CLI is unchanged. When the flag is set, the active
    connection's ``current_database()`` must be
    ``baseball_intelligence_test``. The configured ``DATABASE_URL`` is
    not trusted as a substitute for that live check.
    """
    if not alembic_test_database_guard_enabled(environ):
        return
    connected_name = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()
    if connected_name != REQUIRED_TEST_DATABASE_NAME:
        raise DatabaseConfigurationError(
            "Alembic test guard requires the active database to be "
            f"{REQUIRED_TEST_DATABASE_NAME}, not '{connected_name}'."
        )


def require_connected_test_database(engine: Engine) -> None:
    """Fail unless the live connection and Alembic URL use the test database.

    Schema tests must call this after pointing Alembic at the guarded
    test URL and before any upgrade, downgrade, or recovery command.
    """
    if not alembic_test_database_guard_enabled():
        raise DatabaseConfigurationError(
            "Alembic test guard must be active before schema operations."
        )
    with engine.connect() as connection:
        connected_name = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()
    if connected_name != REQUIRED_TEST_DATABASE_NAME:
        raise DatabaseConfigurationError(
            "Destructive schema operations require the connected "
            f"database to be {REQUIRED_TEST_DATABASE_NAME}, not "
            f"'{connected_name}'."
        )

    alembic_url = os.environ.get("DATABASE_URL", "").strip()
    if not alembic_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL must be set to the test database before "
            "Alembic commands run."
        )
    try:
        alembic_database = make_url(alembic_url).database
    except ArgumentError:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not a valid SQLAlchemy URL."
        ) from None
    if alembic_database != REQUIRED_TEST_DATABASE_NAME:
        raise DatabaseConfigurationError(
            "DATABASE_URL must point at "
            f"{REQUIRED_TEST_DATABASE_NAME} while Alembic commands run."
        )


def _restore_environ(name: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


@contextmanager
def configure_alembic_test_database() -> Iterator[None]:
    """Temporarily point in-process Alembic commands at the test database.

    Alembic's env.py reads DATABASE_URL. Tests set that variable to the
    already-validated TEST_DATABASE_URL so upgrade/downgrade cannot
    target the development database. An explicit test-guard flag is also
    set so env.py verifies Alembic's own ``current_database()`` before
    running migrations. Both values are restored even if Alembic raises.
    python-dotenv will not override existing environment variables.
    """
    test_url = get_test_database_url()
    previous_url = os.environ.get("DATABASE_URL")
    previous_guard = os.environ.get(ALEMBIC_TEST_DATABASE_GUARD_ENV)
    os.environ["DATABASE_URL"] = test_url
    os.environ[ALEMBIC_TEST_DATABASE_GUARD_ENV] = ALEMBIC_TEST_DATABASE_GUARD_VALUE
    try:
        yield
    finally:
        _restore_environ("DATABASE_URL", previous_url)
        _restore_environ(ALEMBIC_TEST_DATABASE_GUARD_ENV, previous_guard)
