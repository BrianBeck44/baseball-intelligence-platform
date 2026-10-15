"""Integration tests for curated Statcast loading orchestration."""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, call, patch

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.game_data import GameLoadResult
from app.curated.game_player_data import GamePlayerLoadResult
from app.curated.game_team_data import GameTeamLoadResult
from app.curated.load_all import CuratedLoadResult, load_all_curated
from app.curated.pitch_loader import PitchLoadOrchestrationResult
from app.curated.plate_appearance_loader import (
    PlateAppearanceLoadOrchestrationResult,
)
from app.curated.player_loader import PlayerLoadResult
from app.curated.season_data import SeasonLoadResult
from app.ingestion.batch import create_ingestion_batch


_CURATED_TABLES = (
    "season",
    "team",
    "player",
    "game",
    "game_team",
    "game_player",
    "plate_appearance",
    "pitch",
)


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


def _count_table(connection: Connection, table_name: str) -> int:
    return connection.execute(
        text(f"SELECT COUNT(*) FROM curated.{table_name}")
    ).scalar_one()


def _curated_counts(connection: Connection) -> dict[str, int]:
    return {
        table_name: _count_table(connection, table_name)
        for table_name in _CURATED_TABLES
    }


def _clear_statcast_pitches(connection: Connection) -> None:
    connection.execute(text("DELETE FROM raw.statcast_pitch"))


def _insert_game_type(connection: Connection, code: str, name: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO curated.game_type (code, name)
            VALUES (:code, :name)
            """
        ),
        {"code": code, "name": name},
    )


def _insert_team(connection: Connection, code: str, name: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO curated.team (code, name)
            VALUES (:code, :name)
            """
        ),
        {"code": code, "name": name},
    )


def _insert_player(
    connection: Connection,
    mlb_player_id: int,
    full_name: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO curated.player (mlb_player_id, full_name)
            VALUES (:mlb_player_id, :full_name)
            """
        ),
        {"mlb_player_id": mlb_player_id, "full_name": full_name},
    )


def _insert_statcast_pitch(connection: Connection) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name="pytest_load_all_statcast_pitch",
        started_at=datetime.now(timezone.utc),
    )
    connection.execute(
        text(
            """
            INSERT INTO raw.statcast_pitch (
                ingestion_batch_id,
                game_pk,
                at_bat_number,
                pitch_number,
                game_date,
                game_type,
                batter,
                pitcher,
                home_team,
                away_team,
                inning,
                inning_topbot,
                stand,
                p_throws
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                :at_bat_number,
                :pitch_number,
                :game_date,
                :game_type,
                :batter,
                :pitcher,
                :home_team,
                :away_team,
                :inning,
                :inning_topbot,
                :stand,
                :p_throws
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": 900008001,
            "at_bat_number": 1,
            "pitch_number": 1,
            "game_date": date(2022, 4, 8),
            "game_type": "ZLL",
            "batter": 888020101,
            "pitcher": 888020102,
            "home_team": "ZLL",
            "away_team": "ZLM",
            "inning": 1,
            "inning_topbot": "Top",
            "stand": "L",
            "p_throws": "R",
        },
    )


def _seed_pipeline_inputs(connection: Connection) -> None:
    _clear_statcast_pitches(connection)
    _insert_game_type(connection, "ZLL", "Zeta Load All Regular")
    _insert_team(connection, "ZLL", "Zeta Load All Home")
    _insert_team(connection, "ZLM", "Zeta Load All Away")
    _insert_player(connection, 888020101, "Ada Load All Batter")
    _insert_player(connection, 888020102, "Pat Load All Pitcher")
    _insert_statcast_pitch(connection)


def test_load_all_curated_calls_loaders_in_dependency_order():
    connection = MagicMock()
    seasons = SeasonLoadResult(seasons_loaded=5)
    players = PlayerLoadResult(
        player_ids_found=2,
        players_resolved=2,
        players_loaded=2,
    )
    games = GameLoadResult(games_supplied=1, games_loaded=1)
    game_teams = GameTeamLoadResult(game_teams_supplied=2, game_teams_loaded=2)
    game_players = GamePlayerLoadResult(
        game_players_supplied=2,
        game_players_loaded=2,
    )
    plate_appearances = PlateAppearanceLoadOrchestrationResult(
        plate_appearances_found=1,
        plate_appearances_loaded=1,
    )
    pitches = PitchLoadOrchestrationResult(pitches_found=1, pitches_loaded=1)

    with (
        patch(
            "app.curated.load_all.load_mlb_seasons",
            return_value=seasons,
        ) as mock_seasons,
        patch(
            "app.curated.load_all.load_teams_from_mlb_stats_api",
            return_value=30,
        ) as mock_teams,
        patch(
            "app.curated.load_all.load_players_from_statcast",
            return_value=players,
        ) as mock_players,
        patch(
            "app.curated.load_all.load_games_from_statcast",
            return_value=games,
        ) as mock_games,
        patch(
            "app.curated.load_all.load_game_teams_from_statcast",
            return_value=game_teams,
        ) as mock_game_teams,
        patch(
            "app.curated.load_all.load_game_players_from_statcast",
            return_value=game_players,
        ) as mock_game_players,
        patch(
            "app.curated.load_all.load_plate_appearances_from_statcast",
            return_value=plate_appearances,
        ) as mock_plate_appearances,
        patch(
            "app.curated.load_all.load_pitches_from_statcast",
            return_value=pitches,
        ) as mock_pitches,
    ):
        manager = MagicMock()
        manager.attach_mock(mock_seasons, "load_mlb_seasons")
        manager.attach_mock(mock_teams, "load_teams_from_mlb_stats_api")
        manager.attach_mock(mock_players, "load_players_from_statcast")
        manager.attach_mock(mock_games, "load_games_from_statcast")
        manager.attach_mock(mock_game_teams, "load_game_teams_from_statcast")
        manager.attach_mock(
            mock_game_players,
            "load_game_players_from_statcast",
        )
        manager.attach_mock(
            mock_plate_appearances,
            "load_plate_appearances_from_statcast",
        )
        manager.attach_mock(mock_pitches, "load_pitches_from_statcast")

        result = load_all_curated(connection)

    assert manager.mock_calls == [
        call.load_mlb_seasons(connection),
        call.load_teams_from_mlb_stats_api(connection),
        call.load_players_from_statcast(connection),
        call.load_games_from_statcast(connection),
        call.load_game_teams_from_statcast(connection),
        call.load_game_players_from_statcast(connection),
        call.load_plate_appearances_from_statcast(connection),
        call.load_pitches_from_statcast(connection),
    ]
    mock_teams.assert_called_once_with(connection)
    mock_players.assert_called_once_with(connection)
    assert result.teams == 30
    assert result == CuratedLoadResult(
        seasons=seasons,
        teams=30,
        players=players,
        games=games,
        game_teams=game_teams,
        game_players=game_players,
        plate_appearances=plate_appearances,
        pitches=pitches,
    )


def test_load_all_curated_populates_curated_tables():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _seed_pipeline_inputs(connection)

            players = PlayerLoadResult(
                player_ids_found=2,
                players_resolved=2,
                players_loaded=2,
            )
            with (
                patch(
                    "app.curated.load_all.load_teams_from_mlb_stats_api",
                    return_value=30,
                ) as mock_load_teams,
                patch(
                    "app.curated.load_all.load_players_from_statcast",
                    return_value=players,
                ) as mock_load_players,
            ):
                result = load_all_curated(connection)

            mock_load_teams.assert_called_once_with(connection)
            mock_load_players.assert_called_once_with(connection)
            assert isinstance(result, CuratedLoadResult)
            assert isinstance(result.seasons, SeasonLoadResult)
            assert result.teams == 30
            assert isinstance(result.players, PlayerLoadResult)
            assert result.players == players
            assert isinstance(result.games, GameLoadResult)
            assert isinstance(result.game_teams, GameTeamLoadResult)
            assert isinstance(result.game_players, GamePlayerLoadResult)
            assert isinstance(
                result.plate_appearances,
                PlateAppearanceLoadOrchestrationResult,
            )
            assert isinstance(result.pitches, PitchLoadOrchestrationResult)

            counts = _curated_counts(connection)
            assert counts["season"] > 0
            assert counts["team"] > 0
            assert counts["player"] > 0
            assert counts["game"] > 0
            assert counts["game_team"] > 0
            assert counts["game_player"] > 0
            assert counts["plate_appearance"] > 0
            assert counts["pitch"] > 0
    finally:
        engine.dispose()


def test_load_all_curated_does_not_duplicate_business_records():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _seed_pipeline_inputs(connection)

            with (
                patch(
                    "app.curated.load_all.load_teams_from_mlb_stats_api",
                    return_value=30,
                ),
                patch(
                    "app.curated.load_all.load_players_from_statcast",
                    return_value=PlayerLoadResult(
                        player_ids_found=2,
                        players_resolved=2,
                        players_loaded=2,
                    ),
                ),
            ):
                load_all_curated(connection)
                counts_after_first = _curated_counts(connection)

                load_all_curated(connection)
                counts_after_second = _curated_counts(connection)

            assert counts_after_second == counts_after_first
            assert counts_after_first["game"] > 0
            assert counts_after_first["team"] > 0
            assert counts_after_first["player"] > 0
            assert counts_after_first["game_team"] > 0
            assert counts_after_first["game_player"] > 0
            assert counts_after_first["plate_appearance"] > 0
            assert counts_after_first["pitch"] > 0
    finally:
        engine.dispose()
