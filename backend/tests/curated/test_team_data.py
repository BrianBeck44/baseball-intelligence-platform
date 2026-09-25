"""Tests for curated.team upserts."""

from contextlib import contextmanager
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.team_data import load_mlb_teams
from app.mlb.stats_api import MlbTeam


def _create_engine() -> Engine:
    return create_engine(settings.database_url)


@contextmanager
def _isolated_connection(engine: Engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def _fetch_team(connection: Connection, code: str):
    return connection.execute(
        text(
            """
            SELECT team_id, code, name
            FROM curated.team
            WHERE code = :code
            """
        ),
        {"code": code},
    ).mappings().one()


def _count_teams(connection: Connection, codes: list[str]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.team
            WHERE code = ANY(:codes)
            """
        ),
        {"codes": codes},
    ).scalar_one()


def test_empty_input_returns_zero_and_does_not_insert():
    connection = MagicMock()

    result = load_mlb_teams(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()


def test_new_team_is_inserted():
    engine = _create_engine()
    code = "ZZA"

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_teams(
                connection,
                [MlbTeam(code=code, name="Zeta Angels")],
            )

            assert result == 1
            team = _fetch_team(connection, code)
            assert team["code"] == code
            assert team["name"] == "Zeta Angels"
            assert team["team_id"] is not None
    finally:
        engine.dispose()


def test_multiple_teams_can_be_inserted():
    engine = _create_engine()
    first_code = "ZZB"
    second_code = "ZZC"

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_teams(
                connection,
                [
                    MlbTeam(code=first_code, name="Zeta Bats"),
                    MlbTeam(code=second_code, name="Zeta Cats"),
                ],
            )

            assert result == 2
            assert _count_teams(connection, [first_code, second_code]) == 2
            assert _fetch_team(connection, first_code)["name"] == "Zeta Bats"
            assert _fetch_team(connection, second_code)["name"] == "Zeta Cats"
    finally:
        engine.dispose()


def test_duplicate_team_codes_are_deduplicated():
    engine = _create_engine()
    code = "ZZD"

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_teams(
                connection,
                [
                    MlbTeam(code=code, name="Zeta Dogs"),
                    MlbTeam(code=code, name="Zeta Dogs Jr."),
                ],
            )

            assert result == 2
            team = _fetch_team(connection, code)
            assert team["name"] == "Zeta Dogs Jr."
            assert _count_teams(connection, [code]) == 1
    finally:
        engine.dispose()


def test_existing_team_code_updates_name():
    engine = _create_engine()
    code = "ZZE"

    try:
        with _isolated_connection(engine) as connection:
            load_mlb_teams(
                connection,
                [MlbTeam(code=code, name="Zeta Eagles")],
            )
            result = load_mlb_teams(
                connection,
                [MlbTeam(code=code, name="Zeta Eagles Jr.")],
            )

            assert result == 1
            team = _fetch_team(connection, code)
            assert team["name"] == "Zeta Eagles Jr."
    finally:
        engine.dispose()


def test_team_id_is_preserved_when_name_is_updated():
    engine = _create_engine()
    code = "ZZF"

    try:
        with _isolated_connection(engine) as connection:
            load_mlb_teams(
                connection,
                [MlbTeam(code=code, name="Zeta Foxes")],
            )
            original = _fetch_team(connection, code)

            load_mlb_teams(
                connection,
                [MlbTeam(code=code, name="Zeta Foxes Jr.")],
            )
            updated = _fetch_team(connection, code)

            assert updated["team_id"] == original["team_id"]
            assert updated["code"] == code
            assert updated["name"] == "Zeta Foxes Jr."
    finally:
        engine.dispose()


def test_returns_number_of_supplied_team_objects():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_teams(
                connection,
                [
                    MlbTeam(code="ZZG", name="Zeta Giants"),
                    MlbTeam(code="ZZH", name="Zeta Hawks"),
                    MlbTeam(code="ZZG", name="Zeta Giants Jr."),
                ],
            )

            assert result == 3
            assert _count_teams(connection, ["ZZG", "ZZH"]) == 2
    finally:
        engine.dispose()
