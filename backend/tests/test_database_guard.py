"""Regression tests for dedicated test-database configuration.

These tests use in-memory URL strings and do not connect to PostgreSQL.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from tests.db import (
    ALEMBIC_TEST_DATABASE_GUARD_ENV,
    ALEMBIC_TEST_DATABASE_GUARD_VALUE,
    REQUIRED_TEST_DATABASE_NAME,
    DatabaseConfigurationError,
    alembic_test_database_guard_enabled,
    configure_alembic_test_database,
    create_test_engine,
    enforce_alembic_test_database_guard,
    get_test_database_url,
    require_connected_test_database,
)

ALEMBIC_ENV_PATH = Path(__file__).resolve().parents[1] / "alembic" / "env.py"


def _url_for(database_name: str) -> str:
    return (
        "postgresql+psycopg://test_user:test_password@localhost:5432/"
        f"{database_name}"
    )


def _mock_connection(database_name: str) -> MagicMock:
    connection = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = database_name
    connection.execute.return_value = result
    return connection


def _mock_engine(database_name: str) -> MagicMock:
    engine = MagicMock()
    connection = _mock_connection(database_name)
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False
    return engine


def _activate_alembic_test_guard(monkeypatch, database_url: str | None = None):
    monkeypatch.setenv(
        ALEMBIC_TEST_DATABASE_GUARD_ENV,
        ALEMBIC_TEST_DATABASE_GUARD_VALUE,
    )
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)


def test_missing_test_database_url_raises():
    with pytest.raises(
        DatabaseConfigurationError,
        match="TEST_DATABASE_URL is not set",
    ):
        get_test_database_url(environ={})


def test_empty_test_database_url_raises():
    with pytest.raises(
        DatabaseConfigurationError,
        match="TEST_DATABASE_URL is not set",
    ):
        get_test_database_url(environ={"TEST_DATABASE_URL": "   "})


def test_database_url_is_not_used_as_fallback():
    with pytest.raises(
        DatabaseConfigurationError,
        match="do not use DATABASE_URL",
    ):
        get_test_database_url(
            environ={
                "DATABASE_URL": _url_for("baseball_intelligence"),
            }
        )


def test_ignores_database_url_when_test_url_is_set():
    resolved = get_test_database_url(
        environ={
            "DATABASE_URL": _url_for("baseball_intelligence"),
            "TEST_DATABASE_URL": _url_for(REQUIRED_TEST_DATABASE_NAME),
        }
    )

    assert make_url(resolved).database == REQUIRED_TEST_DATABASE_NAME


def test_rejects_development_database_name():
    with pytest.raises(
        DatabaseConfigurationError,
        match="must not point at the development database",
    ):
        get_test_database_url(
            environ={"TEST_DATABASE_URL": _url_for("baseball_intelligence")}
        )


def test_rejects_unexpected_database_name():
    with pytest.raises(
        DatabaseConfigurationError,
        match="must use database baseball_intelligence_test",
    ):
        get_test_database_url(
            environ={"TEST_DATABASE_URL": _url_for("postgres")}
        )


def test_rejects_sqlite_url():
    with pytest.raises(
        DatabaseConfigurationError,
        match="must be a PostgreSQL SQLAlchemy URL",
    ) as exc_info:
        get_test_database_url(
            environ={
                "TEST_DATABASE_URL": (
                    "sqlite:///baseball_intelligence_test"
                )
            }
        )

    message = str(exc_info.value)
    assert "sqlite:///baseball_intelligence_test" not in message


def test_rejects_non_postgresql_scheme_without_leaking_credentials():
    secret_url = (
        "mysql+pymysql://test_user:super-secret@localhost:3306/"
        "baseball_intelligence_test"
    )
    with pytest.raises(
        DatabaseConfigurationError,
        match="must be a PostgreSQL SQLAlchemy URL",
    ) as exc_info:
        get_test_database_url(environ={"TEST_DATABASE_URL": secret_url})

    message = str(exc_info.value)
    assert "super-secret" not in message
    assert "test_user" not in message
    assert secret_url not in message


def test_accepts_postgresql_url_without_driver_suffix():
    url_text = (
        "postgresql://test_user:test_password@localhost:5432/"
        f"{REQUIRED_TEST_DATABASE_NAME}"
    )
    resolved = get_test_database_url(environ={"TEST_DATABASE_URL": url_text})

    assert resolved == url_text
    assert make_url(resolved).get_backend_name() == "postgresql"


def test_rejects_url_without_database_name():
    with pytest.raises(
        DatabaseConfigurationError,
        match="must include a database name",
    ):
        get_test_database_url(
            environ={
                "TEST_DATABASE_URL": (
                    "postgresql+psycopg://test_user:test_password@localhost:5432"
                )
            }
        )


def test_rejects_malformed_url_without_leaking_credentials(monkeypatch):
    secret_url = "postgresql+psycopg://test_user:super-secret@localhost:5432/db"

    def _raise_invalid(url_text: str):
        raise ArgumentError(f"Could not parse URL '{url_text}'")

    monkeypatch.setattr("tests.db.make_url", _raise_invalid)

    with pytest.raises(
        DatabaseConfigurationError,
        match="not a valid SQLAlchemy URL",
    ) as exc_info:
        get_test_database_url(environ={"TEST_DATABASE_URL": secret_url})

    message = str(exc_info.value)
    assert "super-secret" not in message
    assert secret_url not in message


def test_accepts_baseball_intelligence_test():
    url_text = _url_for(REQUIRED_TEST_DATABASE_NAME)
    resolved = get_test_database_url(
        environ={"TEST_DATABASE_URL": url_text}
    )

    assert resolved == url_text
    assert make_url(resolved).database == REQUIRED_TEST_DATABASE_NAME


def test_error_messages_do_not_include_credentials():
    secret_url = (
        "postgresql+psycopg://test_user:super-secret@localhost:5432/"
        "baseball_intelligence"
    )
    with pytest.raises(DatabaseConfigurationError) as exc_info:
        get_test_database_url(environ={"TEST_DATABASE_URL": secret_url})

    message = str(exc_info.value)
    assert "super-secret" not in message
    assert "test_user" not in message
    assert secret_url not in message


def test_configure_alembic_uses_guarded_test_url_then_restores(monkeypatch):
    test_url = _url_for(REQUIRED_TEST_DATABASE_NAME)
    original = _url_for("baseball_intelligence")
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", original)
    monkeypatch.delenv(ALEMBIC_TEST_DATABASE_GUARD_ENV, raising=False)

    with configure_alembic_test_database():
        assert os.environ["DATABASE_URL"] == test_url
        assert (
            os.environ[ALEMBIC_TEST_DATABASE_GUARD_ENV]
            == ALEMBIC_TEST_DATABASE_GUARD_VALUE
        )

    assert os.environ["DATABASE_URL"] == original
    assert ALEMBIC_TEST_DATABASE_GUARD_ENV not in os.environ


def test_configure_alembic_restores_when_database_url_was_unset(monkeypatch):
    test_url = _url_for(REQUIRED_TEST_DATABASE_NAME)
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv(ALEMBIC_TEST_DATABASE_GUARD_ENV, raising=False)

    with configure_alembic_test_database():
        assert os.environ["DATABASE_URL"] == test_url
        assert alembic_test_database_guard_enabled()

    assert "DATABASE_URL" not in os.environ
    assert ALEMBIC_TEST_DATABASE_GUARD_ENV not in os.environ


def test_configure_alembic_restores_previous_guard_flag_after_exception(
    monkeypatch,
):
    test_url = _url_for(REQUIRED_TEST_DATABASE_NAME)
    original = _url_for("baseball_intelligence")
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", original)
    monkeypatch.setenv(ALEMBIC_TEST_DATABASE_GUARD_ENV, "0")

    with pytest.raises(RuntimeError, match="alembic failed"):
        with configure_alembic_test_database():
            assert os.environ["DATABASE_URL"] == test_url
            assert (
                os.environ[ALEMBIC_TEST_DATABASE_GUARD_ENV]
                == ALEMBIC_TEST_DATABASE_GUARD_VALUE
            )
            raise RuntimeError("alembic failed")

    assert os.environ["DATABASE_URL"] == original
    assert os.environ[ALEMBIC_TEST_DATABASE_GUARD_ENV] == "0"


def test_configure_alembic_does_not_change_env_when_test_url_is_invalid(
    monkeypatch,
):
    original = _url_for("baseball_intelligence")
    monkeypatch.setenv("DATABASE_URL", original)
    monkeypatch.setenv("TEST_DATABASE_URL", original)
    monkeypatch.delenv(ALEMBIC_TEST_DATABASE_GUARD_ENV, raising=False)

    with pytest.raises(
        DatabaseConfigurationError,
        match="must not point at the development database",
    ):
        with configure_alembic_test_database():
            pass

    assert os.environ["DATABASE_URL"] == original
    assert ALEMBIC_TEST_DATABASE_GUARD_ENV not in os.environ


def test_alembic_test_database_guard_is_disabled_without_explicit_flag():
    assert alembic_test_database_guard_enabled(environ={}) is False
    assert alembic_test_database_guard_enabled(
        environ={ALEMBIC_TEST_DATABASE_GUARD_ENV: "true"}
    ) is False
    assert alembic_test_database_guard_enabled(
        environ={ALEMBIC_TEST_DATABASE_GUARD_ENV: "0"}
    ) is False


def test_enforce_alembic_guard_is_noop_when_flag_is_inactive():
    connection = _mock_connection("baseball_intelligence")

    enforce_alembic_test_database_guard(connection, environ={})

    connection.execute.assert_not_called()


def test_enforce_alembic_guard_accepts_test_database_when_active():
    connection = _mock_connection(REQUIRED_TEST_DATABASE_NAME)

    enforce_alembic_test_database_guard(
        connection,
        environ={
            ALEMBIC_TEST_DATABASE_GUARD_ENV: ALEMBIC_TEST_DATABASE_GUARD_VALUE,
            "DATABASE_URL": _url_for("baseball_intelligence"),
        },
    )

    connection.execute.assert_called_once()


def test_enforce_alembic_guard_rejects_development_connection_when_active():
    connection = _mock_connection("baseball_intelligence")

    with pytest.raises(
        DatabaseConfigurationError,
        match="Alembic test guard requires the active database",
    ):
        enforce_alembic_test_database_guard(
            connection,
            environ={
                ALEMBIC_TEST_DATABASE_GUARD_ENV: ALEMBIC_TEST_DATABASE_GUARD_VALUE,
                "DATABASE_URL": _url_for(REQUIRED_TEST_DATABASE_NAME),
            },
        )


def test_require_connected_test_database_accepts_test_database(monkeypatch):
    _activate_alembic_test_guard(
        monkeypatch,
        _url_for(REQUIRED_TEST_DATABASE_NAME),
    )

    require_connected_test_database(_mock_engine(REQUIRED_TEST_DATABASE_NAME))


def test_require_connected_test_database_rejects_inactive_guard(monkeypatch):
    monkeypatch.delenv(ALEMBIC_TEST_DATABASE_GUARD_ENV, raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        _url_for(REQUIRED_TEST_DATABASE_NAME),
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="Alembic test guard must be active",
    ):
        require_connected_test_database(
            _mock_engine(REQUIRED_TEST_DATABASE_NAME)
        )


def test_require_connected_test_database_rejects_development_connection(
    monkeypatch,
):
    _activate_alembic_test_guard(
        monkeypatch,
        _url_for(REQUIRED_TEST_DATABASE_NAME),
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="connected database to be baseball_intelligence_test",
    ):
        require_connected_test_database(_mock_engine("baseball_intelligence"))


def test_require_connected_test_database_rejects_development_alembic_url(
    monkeypatch,
):
    _activate_alembic_test_guard(
        monkeypatch,
        _url_for("baseball_intelligence"),
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="DATABASE_URL must point at baseball_intelligence_test",
    ):
        require_connected_test_database(
            _mock_engine(REQUIRED_TEST_DATABASE_NAME)
        )


def test_require_connected_test_database_rejects_missing_alembic_url(
    monkeypatch,
):
    _activate_alembic_test_guard(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(
        DatabaseConfigurationError,
        match="DATABASE_URL must be set to the test database",
    ):
        require_connected_test_database(
            _mock_engine(REQUIRED_TEST_DATABASE_NAME)
        )


def test_alembic_env_verifies_current_database_before_migrations():
    source = ALEMBIC_ENV_PATH.read_text()
    online_source = source.split("def run_migrations_online", 1)[1]
    offline_source = source.split("def run_migrations_offline", 1)[1].split(
        "def run_migrations_online", 1
    )[0]

    assert ALEMBIC_TEST_DATABASE_GUARD_ENV in source
    assert "SELECT current_database()" in source
    assert REQUIRED_TEST_DATABASE_NAME in source
    assert "_require_alembic_connection_is_test_database(connection)" in (
        online_source
    )
    assert online_source.index(
        "_require_alembic_connection_is_test_database(connection)"
    ) < online_source.index("context.run_migrations()")
    assert "forbids offline migrations" in offline_source


def test_create_test_engine_rejects_development_database(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        _url_for("baseball_intelligence"),
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="must not point at the development database",
    ):
        create_test_engine()
