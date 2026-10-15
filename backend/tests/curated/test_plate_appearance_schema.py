"""Schema tests for curated.plate_appearance."""

from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from tests.db import (
    configure_alembic_test_database,
    create_test_engine,
    require_connected_test_database,
)


PLATE_APPEARANCE_REVISION = "d8a1c4f27b90"
PREVIOUS_REVISION = "f1a9c3e84b06"
CREATE_TABLE_REVISION = "c9e2b7a15d04"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _engine():
    return create_test_engine()


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


@contextmanager
def _alembic_on_test_database(engine):
    with configure_alembic_test_database():
        require_connected_test_database(engine)
        yield _alembic_config()


def _fetch_columns(connection):
    return connection.execute(
        text(
            """
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'curated'
              AND table_name = 'plate_appearance'
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
              AND rel.relname = 'plate_appearance'
            ORDER BY con.conname
            """
        )
    ).mappings().all()


def _alembic_version(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def _position_at_revision(engine, config, revision: str) -> None:
    current = _alembic_version(engine)
    if current == revision:
        return
    script = ScriptDirectory.from_config(config)
    already_at_or_after = any(
        rev.revision == revision
        for rev in script.walk_revisions(base="base", head=current)
    )
    if already_at_or_after:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


def _table_exists(connection) -> bool:
    return connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'curated'
                  AND table_name = 'plate_appearance'
            )
            """
        )
    ).scalar_one()


def test_plate_appearance_table_has_expected_columns():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            assert _table_exists(connection) is True
            columns = {
                row["column_name"]: row for row in _fetch_columns(connection)
            }

            assert set(columns) == {
                "plate_appearance_id",
                "game_id",
                "at_bat_number",
                "batter_id",
                "pitcher_id",
                "batter_team_id",
                "pitcher_team_id",
                "inning",
                "inning_topbot",
                "outcome_type_id",
                "stand",
                "p_throws",
            }
            assert columns["plate_appearance_id"]["data_type"] == "bigint"
            assert columns["game_id"]["data_type"] == "bigint"
            assert columns["at_bat_number"]["data_type"] == "integer"
            assert columns["batter_id"]["data_type"] == "bigint"
            assert columns["pitcher_id"]["data_type"] == "bigint"
            assert columns["batter_team_id"]["data_type"] == "bigint"
            assert columns["pitcher_team_id"]["data_type"] == "bigint"
            assert columns["inning"]["data_type"] == "smallint"
            assert columns["inning_topbot"]["data_type"] == "character varying"
            assert columns["inning_topbot"]["character_maximum_length"] == 3
            assert columns["outcome_type_id"]["data_type"] == "integer"
            assert columns["stand"]["data_type"] == "character varying"
            assert columns["stand"]["character_maximum_length"] == 1
            assert columns["p_throws"]["data_type"] == "character varying"
            assert columns["p_throws"]["character_maximum_length"] == 1
    finally:
        engine.dispose()


def test_plate_appearance_primary_key_exists():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "pk_plate_appearance" in constraints
            assert constraints["pk_plate_appearance"]["contype"] == "p"
            assert "plate_appearance_id" in constraints["pk_plate_appearance"][
                "definition"
            ]
    finally:
        engine.dispose()


def test_plate_appearance_game_id_at_bat_number_is_unique():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "uq_plate_appearance_game_at_bat" in constraints
            assert constraints["uq_plate_appearance_game_at_bat"]["contype"] == "u"
            definition = constraints["uq_plate_appearance_game_at_bat"]["definition"]
            assert "game_id" in definition
            assert "at_bat_number" in definition
    finally:
        engine.dispose()


def test_plate_appearance_foreign_keys():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }

            assert "fk_plate_appearance_game" in constraints
            assert constraints["fk_plate_appearance_game"]["contype"] == "f"
            assert "game_id" in constraints["fk_plate_appearance_game"]["definition"]
            assert "curated.game(game_id)" in constraints[
                "fk_plate_appearance_game"
            ]["definition"]

            assert "fk_plate_appearance_batter" in constraints
            assert constraints["fk_plate_appearance_batter"]["contype"] == "f"
            assert "batter_id" in constraints["fk_plate_appearance_batter"][
                "definition"
            ]
            assert "curated.player(player_id)" in constraints[
                "fk_plate_appearance_batter"
            ]["definition"]

            assert "fk_plate_appearance_pitcher" in constraints
            assert constraints["fk_plate_appearance_pitcher"]["contype"] == "f"
            assert "pitcher_id" in constraints["fk_plate_appearance_pitcher"][
                "definition"
            ]
            assert "curated.player(player_id)" in constraints[
                "fk_plate_appearance_pitcher"
            ]["definition"]

            assert "fk_plate_appearance_batter_team" in constraints
            assert constraints["fk_plate_appearance_batter_team"]["contype"] == "f"
            assert "batter_team_id" in constraints[
                "fk_plate_appearance_batter_team"
            ]["definition"]
            assert "curated.team(team_id)" in constraints[
                "fk_plate_appearance_batter_team"
            ]["definition"]

            assert "fk_plate_appearance_pitcher_team" in constraints
            assert constraints["fk_plate_appearance_pitcher_team"]["contype"] == "f"
            assert "pitcher_team_id" in constraints[
                "fk_plate_appearance_pitcher_team"
            ]["definition"]
            assert "curated.team(team_id)" in constraints[
                "fk_plate_appearance_pitcher_team"
            ]["definition"]

            assert "fk_plate_appearance_outcome_type" in constraints
            assert constraints["fk_plate_appearance_outcome_type"]["contype"] == "f"
            assert "outcome_type_id" in constraints[
                "fk_plate_appearance_outcome_type"
            ]["definition"]
            assert "curated.outcome_type(id)" in constraints[
                "fk_plate_appearance_outcome_type"
            ]["definition"]
    finally:
        engine.dispose()


def test_required_plate_appearance_columns_are_not_null():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            columns = {
                row["column_name"]: row for row in _fetch_columns(connection)
            }
            assert columns["outcome_type_id"]["is_nullable"] == "YES"
            required = {
                name: row
                for name, row in columns.items()
                if name != "outcome_type_id"
            }
            assert set(required) == {
                "plate_appearance_id",
                "game_id",
                "at_bat_number",
                "batter_id",
                "pitcher_id",
                "batter_team_id",
                "pitcher_team_id",
                "inning",
                "inning_topbot",
                "stand",
                "p_throws",
            }
            assert all(row["is_nullable"] == "NO" for row in required.values())
    finally:
        engine.dispose()


def test_inning_topbot_check_constraint_exists():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "ck_plate_appearance_inning_topbot" in constraints
            assert constraints["ck_plate_appearance_inning_topbot"]["contype"] == "c"
            definition = constraints["ck_plate_appearance_inning_topbot"][
                "definition"
            ]
            assert "Top" in definition
            assert "Bot" in definition
    finally:
        engine.dispose()


def test_stand_and_p_throws_check_constraints_exist():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            command.upgrade(config, PLATE_APPEARANCE_REVISION)

        with engine.connect() as connection:
            constraints = {
                row["conname"]: row for row in _fetch_constraints(connection)
            }
            assert "ck_plate_appearance_stand" in constraints
            assert constraints["ck_plate_appearance_stand"]["contype"] == "c"
            stand_definition = constraints["ck_plate_appearance_stand"]["definition"]
            assert "stand" in stand_definition
            assert "'L'" in stand_definition
            assert "'R'" in stand_definition
            assert "'S'" in stand_definition

            assert "ck_plate_appearance_p_throws" in constraints
            assert constraints["ck_plate_appearance_p_throws"]["contype"] == "c"
            throws_definition = constraints["ck_plate_appearance_p_throws"][
                "definition"
            ]
            assert "p_throws" in throws_definition
            assert "'L'" in throws_definition
            assert "'R'" in throws_definition
    finally:
        engine.dispose()


def test_downgrade_removes_stand_and_p_throws():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            try:
                require_connected_test_database(engine)
                _position_at_revision(engine, config, PLATE_APPEARANCE_REVISION)
                assert _alembic_version(engine) == PLATE_APPEARANCE_REVISION

                require_connected_test_database(engine)
                command.upgrade(config, PLATE_APPEARANCE_REVISION)
                assert _alembic_version(engine) == PLATE_APPEARANCE_REVISION

                require_connected_test_database(engine)
                command.downgrade(config, CREATE_TABLE_REVISION)
                assert _alembic_version(engine) == CREATE_TABLE_REVISION

                with engine.connect() as connection:
                    assert _table_exists(connection) is True
                    columns = {
                        row["column_name"]: row
                        for row in _fetch_columns(connection)
                    }
                    assert "stand" not in columns
                    assert "p_throws" not in columns
                    constraints = {
                        row["conname"]: row
                        for row in _fetch_constraints(connection)
                    }
                    assert "ck_plate_appearance_stand" not in constraints
                    assert "ck_plate_appearance_p_throws" not in constraints
                    assert "pk_plate_appearance" in constraints
                    assert "uq_plate_appearance_game_at_bat" in constraints
            finally:
                require_connected_test_database(engine)
                command.upgrade(config, "head")
    finally:
        engine.dispose()


def test_downgrade_removes_plate_appearance_table():
    engine = _engine()
    try:
        with _alembic_on_test_database(engine) as config:
            try:
                require_connected_test_database(engine)
                _position_at_revision(engine, config, PLATE_APPEARANCE_REVISION)
                assert _alembic_version(engine) == PLATE_APPEARANCE_REVISION

                require_connected_test_database(engine)
                command.upgrade(config, PLATE_APPEARANCE_REVISION)
                assert _alembic_version(engine) == PLATE_APPEARANCE_REVISION

                with engine.connect() as connection:
                    assert _table_exists(connection) is True

                require_connected_test_database(engine)
                command.downgrade(config, PREVIOUS_REVISION)
                assert _alembic_version(engine) == PREVIOUS_REVISION

                with engine.connect() as connection:
                    assert _table_exists(connection) is False
                    constraints = _fetch_constraints(connection)
                    assert constraints == []
            finally:
                require_connected_test_database(engine)
                command.upgrade(config, "head")
    finally:
        engine.dispose()
