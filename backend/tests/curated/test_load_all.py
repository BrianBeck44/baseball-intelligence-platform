"""Integration tests for curated Statcast loading orchestration."""

from contextlib import contextmanager
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.game_data import GameLoadResult
from app.curated.game_player_data import GamePlayerLoadResult
from app.curated.game_team_data import GameTeamLoadResult
from app.curated.load_all import CuratedLoadResult, load_all_curated
from app.curated.pitch_loader import PitchLoadOrchestrationResult
from app.curated.plate_appearance_loader import (
    PlateAppearanceLoadOrchestrationResult,
)
from app.curated.season_data import SeasonLoadResult
from app.ingestion.batch import create_ingestion_batch


_CURATED_TABLES = (
    "season",
    "game",
    "game_team",
    "game_player",
    "plate_appearance",
    "pitch",
)


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


def test_load_all_curated_populates_curated_tables():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _seed_pipeline_inputs(connection)

            result = load_all_curated(connection)

            assert isinstance(result, CuratedLoadResult)
            assert isinstance(result.seasons, SeasonLoadResult)
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

            load_all_curated(connection)
            counts_after_first = _curated_counts(connection)

            load_all_curated(connection)
            counts_after_second = _curated_counts(connection)

            assert counts_after_second == counts_after_first
            assert counts_after_first["game"] > 0
            assert counts_after_first["game_team"] > 0
            assert counts_after_first["game_player"] > 0
            assert counts_after_first["plate_appearance"] > 0
            assert counts_after_first["pitch"] > 0
    finally:
        engine.dispose()
