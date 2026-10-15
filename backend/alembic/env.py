import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy import text

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load backend/.env if present so local DATABASE_URL can be set there.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Export it or add it to backend/.env."
    )

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# Set only by tests.db.configure_alembic_test_database(). The development
# Alembic CLI leaves this unset and is unchanged.
_ALEMBIC_TEST_DATABASE_GUARD_ENV = "ALEMBIC_TEST_DATABASE_GUARD"
_ALEMBIC_TEST_DATABASE_GUARD_VALUE = "1"
_REQUIRED_TEST_DATABASE_NAME = "baseball_intelligence_test"

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def _alembic_test_database_guard_is_active() -> bool:
    return (
        os.environ.get(_ALEMBIC_TEST_DATABASE_GUARD_ENV, "").strip()
        == _ALEMBIC_TEST_DATABASE_GUARD_VALUE
    )


def _require_alembic_connection_is_test_database(connection) -> None:
    """Abort guarded schema tests that are not on baseball_intelligence_test.

    The live connection is authoritative. A stale or incorrect
    DATABASE_URL cannot bypass this check.
    """
    if not _alembic_test_database_guard_is_active():
        return
    connected_name = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()
    if connected_name != _REQUIRED_TEST_DATABASE_NAME:
        raise RuntimeError(
            "Alembic test guard requires the active database to be "
            f"{_REQUIRED_TEST_DATABASE_NAME}."
        )
    # The guard SELECT autobegins a SQLAlchemy 2.x transaction. Alembic
    # treats that as an external transaction and will not commit
    # migration DDL. Roll it back so Alembic can manage its own
    # transaction. Reached only when the test guard is active.
    if connection.in_transaction():
        connection.rollback()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    if _alembic_test_database_guard_is_active():
        raise RuntimeError(
            "Alembic test guard forbids offline migrations because the "
            "active database cannot be verified."
        )
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        _require_alembic_connection_is_test_database(connection)
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
