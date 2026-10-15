"""Tests for source-derived analytics rebuild validation."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.load_all import AnalyticsLoadResult, SeasonLoadResult
from app.analytics.player_game_batting_loader import PlayerGameBattingLoadResult
from app.analytics.player_game_pitching_loader import PlayerGamePitchingLoadResult
from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
)
from app.analytics.rebuild_validation import (
    _raise_if_mismatched,
    require_curated_rebuild_sources,
    validate_analytics_rebuild,
    validate_player_game_batting_load,
)
from tests.db import create_test_engine


def _create_engine() -> Engine:
    return create_test_engine()


@contextmanager
def _isolated_connection(engine: Engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def _zero_rebuild_result() -> AnalyticsLoadResult:
    return AnalyticsLoadResult(
        game_batting=PlayerGameBattingLoadResult(0, 0, 0),
        game_pitching=PlayerGamePitchingLoadResult(0, 0, 0),
        pitch_type_effectiveness=PlayerPitchTypeEffectivenessLoadResult(0, 0, 0),
        season_batting=SeasonLoadResult(0, 0, 0),
        season_pitching=SeasonLoadResult(0, 0, 0),
    )


def _insert_season(connection: Connection, season_year: int) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.season (season_year)
            VALUES (:season_year)
            RETURNING season_id
            """
        ),
        {"season_year": season_year},
    ).scalar_one()


def _insert_game_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_game(
    connection: Connection,
    *,
    mlb_game_pk: int,
    season_id: int,
    game_type_id: int,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game (
                mlb_game_pk,
                season_id,
                official_game_date,
                game_type_id
            )
            VALUES (
                :mlb_game_pk,
                :season_id,
                :official_game_date,
                :game_type_id
            )
            RETURNING game_id
            """
        ),
        {
            "mlb_game_pk": mlb_game_pk,
            "season_id": season_id,
            "official_game_date": date(2298, 4, 8),
            "game_type_id": game_type_id,
        },
    ).scalar_one()


def _insert_player(connection: Connection, mlb_player_id: int, full_name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.player (mlb_player_id, full_name)
            VALUES (:mlb_player_id, :full_name)
            RETURNING player_id
            """
        ),
        {"mlb_player_id": mlb_player_id, "full_name": full_name},
    ).scalar_one()


def _insert_team(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.team (code, name)
            VALUES (:code, :name)
            RETURNING team_id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_plate_appearance(
    connection: Connection,
    *,
    game_id: int,
    batter_id: int,
    pitcher_id: int,
    batter_team_id: int,
    pitcher_team_id: int,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.plate_appearance (
                game_id,
                at_bat_number,
                batter_id,
                pitcher_id,
                batter_team_id,
                pitcher_team_id,
                inning,
                inning_topbot,
                stand,
                p_throws
            )
            VALUES (
                :game_id,
                1,
                :batter_id,
                :pitcher_id,
                :batter_team_id,
                :pitcher_team_id,
                1,
                'Top',
                'L',
                'R'
            )
            RETURNING plate_appearance_id
            """
        ),
        {
            "game_id": game_id,
            "batter_id": batter_id,
            "pitcher_id": pitcher_id,
            "batter_team_id": batter_team_id,
            "pitcher_team_id": pitcher_team_id,
        },
    ).scalar_one()


def _seed_required_curated_sources(connection: Connection) -> None:
    season_id = _insert_season(connection, 2298)
    game_type_id = _insert_game_type(connection, "ZRV", "Zeta Rebuild Validation")
    game_id = _insert_game(
        connection,
        mlb_game_pk=919002002,
        season_id=season_id,
        game_type_id=game_type_id,
    )
    batter_id = _insert_player(connection, 888092201, "Guard Batter")
    pitcher_id = _insert_player(connection, 888092202, "Guard Pitcher")
    batter_team_id = _insert_team(connection, "ZRV", "Zeta Rebuild Validation")
    pitcher_team_id = _insert_team(connection, "ZRW", "Zeta Rebuild West")
    plate_appearance_id = _insert_plate_appearance(
        connection,
        game_id=game_id,
        batter_id=batter_id,
        pitcher_id=pitcher_id,
        batter_team_id=batter_team_id,
        pitcher_team_id=pitcher_team_id,
    )
    connection.execute(
        text(
            """
            INSERT INTO curated.pitch (
                plate_appearance_id,
                pitch_number
            )
            VALUES (
                :plate_appearance_id,
                1
            )
            """
        ),
        {"plate_appearance_id": plate_appearance_id},
    )


def test_raise_if_mismatched_reports_source_derived_counts():
    with pytest.raises(
        ValueError,
        match="player_game_batting load validation failed:\n  rows: expected 4, got 672",
    ):
        _raise_if_mismatched(
            "player_game_batting",
            {"rows": 4},
            {"rows": 672},
        )


def test_raise_if_mismatched_accepts_matching_counts():
    _raise_if_mismatched(
        "player_game_batting",
        {"extracted": 10, "rows": 4},
        {"extracted": 10, "rows": 4},
    )


def test_game_batting_validation_uses_curated_plate_appearance_counts():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            source = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS plate_appearances,
                        COUNT(
                            DISTINCT (batter_id, game_id, batter_team_id)
                        ) AS grains
                    FROM curated.plate_appearance
                    """
                )
            ).mappings().one()
            expected_appearances = int(source["plate_appearances"])
            expected_rows = int(source["grains"])
            assert expected_appearances == int(source["plate_appearances"])
            assert expected_rows == int(source["grains"])

            if expected_appearances == 0 and expected_rows == 0:
                validate_player_game_batting_load(
                    connection,
                    PlayerGameBattingLoadResult(0, 0, 0),
                )
            else:
                with pytest.raises(ValueError, match="extracted"):
                    validate_player_game_batting_load(
                        connection,
                        PlayerGameBattingLoadResult(0, 0, 0),
                    )
    finally:
        engine.dispose()


def test_validation_does_not_manage_transactions():
    connection = MagicMock()
    connection.execute.side_effect = RuntimeError("stop before commit")

    with pytest.raises(RuntimeError, match="stop before commit"):
        validate_player_game_batting_load(
            connection,
            PlayerGameBattingLoadResult(1, 1, 1),
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_rebuild_validation_fails_when_required_sources_are_empty():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "plate_appearance": 0,
        "game": 0,
        "pitch": 0,
    }

    with pytest.raises(
        ValueError,
        match=(
            "Analytics rebuild validation failed: required curated source "
            "tables are empty: curated.plate_appearance, curated.game, "
            "curated.pitch"
        ),
    ):
        validate_analytics_rebuild(connection, _zero_rebuild_result())

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_rebuild_validation_names_a_single_empty_source_table():
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.one.return_value = {
        "plate_appearance": 0,
        "game": 4,
        "pitch": 10,
    }

    with pytest.raises(
        ValueError,
        match=(
            "Analytics rebuild validation failed: required curated source "
            "table is empty: curated.plate_appearance"
        ),
    ):
        require_curated_rebuild_sources(connection)


def test_rebuild_validation_fails_when_sources_exist_but_result_is_zero():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_curated_sources(connection)
            with pytest.raises(ValueError, match="extracted"):
                validate_analytics_rebuild(connection, _zero_rebuild_result())
    finally:
        engine.dispose()


def test_rebuild_validation_rejects_all_zero_result_against_current_database():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with pytest.raises(
                ValueError,
                match="Analytics rebuild validation failed|extracted",
            ):
                validate_analytics_rebuild(connection, _zero_rebuild_result())
    finally:
        engine.dispose()


def test_rebuild_source_precondition_does_not_manage_transactions():
    connection = MagicMock()
    connection.execute.side_effect = RuntimeError("stop before commit")

    with pytest.raises(RuntimeError, match="stop before commit"):
        require_curated_rebuild_sources(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
