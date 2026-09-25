"""Schema tests for curated.game."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings


GAME_REVISION = "7747c1601a99"
PREVIOUS_REVISION = "282f1783779f"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _engine():
    return create_engine(settings.database_url)


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _fetch_columns(connection):
    return connection.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'curated'
              AND table_name = 'game'
            ORDER BY column_name
            """
        )
    ).mappings().all()


def _fetch_constraints(connection):
    return connection.execute(
        text(
            """
            SELECT
                con.conname,
                con.contype,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint AS con
            JOIN pg_class AS rel ON rel.oid = con.conrelid
            JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'curated'
              AND rel.relname = 'game'
            ORDER BY con.conname
            """
        )
    ).mappings().all()


def _table_exists(connection) -> bool:
    return connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'curated'
                  AND table_name = 'game'
            )
            """
        )
    ).scalar_one()


def test_game_table_has_expected_columns():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_REVISION)

    try:
        with engine.connect() as connection:
            columns = {
                row["column_name"]: row for row in _fetch_columns(connection)
            }

            assert set(columns) == {
                "game_id",
                "mlb_game_pk",
                "season_id",
                "official_game_date",
                "game_type_id",
            }
            assert columns["game_id"]["data_type"] == "bigint"
            assert columns["mlb_game_pk"]["data_type"] == "bigint"
            assert columns["season_id"]["data_type"] == "bigint"
            assert columns["official_game_date"]["data_type"] == "date"
            assert columns["game_type_id"]["data_type"] == "integer"
    finally:
        engine.dispose()


def test_game_primary_key_exists():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "pk_game" in constraints
            assert constraints["pk_game"]["contype"] == "p"
            assert "game_id" in constraints["pk_game"]["definition"]
    finally:
        engine.dispose()


def test_game_mlb_game_pk_is_unique():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "uq_game_mlb_game_pk" in constraints
            assert constraints["uq_game_mlb_game_pk"]["contype"] == "u"
            assert "mlb_game_pk" in constraints["uq_game_mlb_game_pk"]["definition"]
    finally:
        engine.dispose()


def test_game_foreign_keys_reference_season_and_game_type():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }

            assert "fk_game_season" in constraints
            assert constraints["fk_game_season"]["contype"] == "f"
            assert "season_id" in constraints["fk_game_season"]["definition"]
            assert "curated.season(season_id)" in constraints["fk_game_season"][
                "definition"
            ]

            assert "fk_game_game_type" in constraints
            assert constraints["fk_game_game_type"]["contype"] == "f"
            assert "game_type_id" in constraints["fk_game_game_type"]["definition"]
            assert "curated.game_type(id)" in constraints["fk_game_game_type"][
                "definition"
            ]
    finally:
        engine.dispose()


def test_required_game_columns_are_not_null():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_REVISION)

    try:
        with engine.connect() as connection:
            columns = _fetch_columns(connection)
            assert {row["column_name"] for row in columns} == {
                "game_id",
                "mlb_game_pk",
                "season_id",
                "official_game_date",
                "game_type_id",
            }
            assert all(row["is_nullable"] == "NO" for row in columns)
    finally:
        engine.dispose()


def test_downgrade_removes_game_table():
    engine = _engine()
    config = _alembic_config()
    command.upgrade(config, GAME_REVISION)

    try:
        with engine.connect() as connection:
            assert _table_exists(connection) is True

        command.downgrade(config, PREVIOUS_REVISION)

        with engine.connect() as connection:
            assert _table_exists(connection) is False
            constraints = _fetch_constraints(connection)
            assert constraints == []
    finally:
        command.upgrade(config, GAME_REVISION)
        engine.dispose()
