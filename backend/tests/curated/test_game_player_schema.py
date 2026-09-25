"""Schema tests for curated.game_player."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings


GAME_PLAYER_REVISION = "f1a9c3e84b06"
PREVIOUS_REVISION = "a3024cf4ca66"
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
              AND table_name = 'game_player'
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
              AND rel.relname = 'game_player'
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
                  AND table_name = 'game_player'
            )
            """
        )
    ).scalar_one()


def test_game_player_table_has_expected_columns():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            columns = {
                row["column_name"]: row for row in _fetch_columns(connection)
            }

            assert set(columns) == {
                "game_player_id",
                "game_id",
                "player_id",
                "team_id",
            }
            assert columns["game_player_id"]["data_type"] == "bigint"
            assert columns["game_id"]["data_type"] == "bigint"
            assert columns["player_id"]["data_type"] == "bigint"
            assert columns["team_id"]["data_type"] == "bigint"
    finally:
        engine.dispose()


def test_game_player_primary_key_exists():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "pk_game_player" in constraints
            assert constraints["pk_game_player"]["contype"] == "p"
            assert "game_player_id" in constraints["pk_game_player"]["definition"]
    finally:
        engine.dispose()


def test_game_player_game_id_player_id_team_id_is_unique():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "uq_game_player_game_player_team" in constraints
            assert constraints["uq_game_player_game_player_team"]["contype"] == "u"
            definition = constraints["uq_game_player_game_player_team"]["definition"]
            assert "game_id" in definition
            assert "player_id" in definition
            assert "team_id" in definition
    finally:
        engine.dispose()


def test_game_player_foreign_keys_reference_game_player_and_team():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }

            assert "fk_game_player_game" in constraints
            assert constraints["fk_game_player_game"]["contype"] == "f"
            assert "game_id" in constraints["fk_game_player_game"]["definition"]
            assert "curated.game(game_id)" in constraints["fk_game_player_game"][
                "definition"
            ]

            assert "fk_game_player_player" in constraints
            assert constraints["fk_game_player_player"]["contype"] == "f"
            assert "player_id" in constraints["fk_game_player_player"]["definition"]
            assert "curated.player(player_id)" in constraints[
                "fk_game_player_player"
            ]["definition"]

            assert "fk_game_player_team" in constraints
            assert constraints["fk_game_player_team"]["contype"] == "f"
            assert "team_id" in constraints["fk_game_player_team"]["definition"]
            assert "curated.team(team_id)" in constraints["fk_game_player_team"][
                "definition"
            ]
    finally:
        engine.dispose()


def test_required_game_player_columns_are_not_null():
    engine = _engine()
    command.upgrade(_alembic_config(), GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            columns = _fetch_columns(connection)
            assert {row["column_name"] for row in columns} == {
                "game_player_id",
                "game_id",
                "player_id",
                "team_id",
            }
            assert all(row["is_nullable"] == "NO" for row in columns)
    finally:
        engine.dispose()


def test_downgrade_removes_game_player_table():
    engine = _engine()
    config = _alembic_config()
    command.upgrade(config, GAME_PLAYER_REVISION)

    try:
        with engine.connect() as connection:
            assert _table_exists(connection) is True

        command.downgrade(config, PREVIOUS_REVISION)

        with engine.connect() as connection:
            assert _table_exists(connection) is False
            constraints = _fetch_constraints(connection)
            assert constraints == []
    finally:
        command.upgrade(config, "head")
        engine.dispose()
