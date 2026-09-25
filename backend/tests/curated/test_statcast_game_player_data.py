"""Tests for distinct game-player extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_game_player_data import (
    StatcastGamePlayer,
    get_statcast_game_players,
)
from app.ingestion.batch import create_ingestion_batch


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


def _clear_statcast_pitches(connection: Connection) -> None:
    connection.execute(text("DELETE FROM raw.statcast_pitch"))


def _insert_pitch(
    connection: Connection,
    *,
    game_pk: int,
    batter: int | None,
    pitcher: int | None,
    home_team: str = "NYY",
    away_team: str = "BOS",
    inning_topbot: str = "Top",
    at_bat_number: int = 1,
    pitch_number: int = 1,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=(
            "pytest_statcast_game_player_data_"
            f"{game_pk}_{at_bat_number}_{pitch_number}"
        ),
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
                batter,
                pitcher,
                home_team,
                away_team,
                inning_topbot
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                :at_bat_number,
                :pitch_number,
                :batter,
                :pitcher,
                :home_team,
                :away_team,
                :inning_topbot
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
            "batter": batter,
            "pitcher": pitcher,
            "home_team": home_team,
            "away_team": away_team,
            "inning_topbot": inning_topbot,
        },
    )


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_game_players(connection) == []
    finally:
        engine.dispose()


def test_one_batter_produces_one_game_player():
    engine = _create_engine()
    game_pk = 900000501

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=None,
                inning_topbot="Bot",
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="NYY",
                )
            ]
    finally:
        engine.dispose()


def test_one_pitcher_produces_one_game_player():
    engine = _create_engine()
    game_pk = 900000502

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=None,
                pitcher=2002,
                inning_topbot="Top",
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="NYY",
                )
            ]
    finally:
        engine.dispose()


def test_multiple_players_in_one_game():
    engine = _create_engine()
    game_pk = 900000503

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Top",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=3003,
                pitcher=2002,
                inning_topbot="Top",
                at_bat_number=2,
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="BOS",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="NYY",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=3003,
                    team_code="BOS",
                ),
            ]
    finally:
        engine.dispose()


def test_players_from_both_teams():
    engine = _create_engine()
    game_pk = 900000504

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Top",
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="BOS",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="NYY",
                ),
            ]
            assert {game_player.team_code for game_player in result} == {
                "BOS",
                "NYY",
            }
    finally:
        engine.dispose()


def test_duplicate_pitches_do_not_create_duplicate_game_players():
    engine = _create_engine()
    game_pk = 900000505

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Top",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Top",
                pitch_number=2,
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="BOS",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="NYY",
                ),
            ]
    finally:
        engine.dispose()


def test_same_player_as_batter_and_pitcher_produces_one_record():
    engine = _create_engine()
    game_pk = 900000506

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Bot",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=3003,
                pitcher=1001,
                inning_topbot="Top",
                at_bat_number=2,
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="NYY",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="BOS",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=3003,
                    team_code="BOS",
                ),
            ]
            assert [
                game_player
                for game_player in result
                if game_player.player_id == 1001
            ] == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="NYY",
                )
            ]
    finally:
        engine.dispose()


def test_same_player_for_different_teams_preserves_both_records():
    engine = _create_engine()
    game_pk = 900000507

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=2002,
                inning_topbot="Top",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=3003,
                inning_topbot="Bot",
                at_bat_number=2,
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="BOS",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=1001,
                    team_code="NYY",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=2002,
                    team_code="NYY",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=game_pk,
                    player_id=3003,
                    team_code="BOS",
                ),
            ]
    finally:
        engine.dispose()


def test_null_batter_and_pitcher_values_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000508,
                batter=None,
                pitcher=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000509,
                batter=None,
                pitcher=2002,
                inning_topbot="Top",
            )
            _insert_pitch(
                connection,
                game_pk=900000510,
                batter=1001,
                pitcher=None,
                inning_topbot="Bot",
            )

            result = get_statcast_game_players(connection)

            assert result == [
                StatcastGamePlayer(
                    mlb_game_pk=900000509,
                    player_id=2002,
                    team_code="NYY",
                ),
                StatcastGamePlayer(
                    mlb_game_pk=900000510,
                    player_id=1001,
                    team_code="NYY",
                ),
            ]
    finally:
        engine.dispose()


def test_results_are_ordered_by_game_player_and_team():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000523,
                batter=50,
                pitcher=None,
                home_team="AAA",
                away_team="ZZB",
                inning_topbot="Top",
            )
            _insert_pitch(
                connection,
                game_pk=900000521,
                batter=None,
                pitcher=40,
                home_team="CCC",
                away_team="BBB",
                inning_topbot="Bot",
            )
            _insert_pitch(
                connection,
                game_pk=900000522,
                batter=20,
                pitcher=10,
                home_team="NYY",
                away_team="BOS",
                inning_topbot="Top",
            )

            result = get_statcast_game_players(connection)

            assert [
                (
                    game_player.mlb_game_pk,
                    game_player.player_id,
                    game_player.team_code,
                )
                for game_player in result
            ] == [
                (900000521, 40, "BBB"),
                (900000522, 10, "NYY"),
                (900000522, 20, "BOS"),
                (900000523, 50, "ZZB"),
            ]
    finally:
        engine.dispose()


def test_returned_values_are_statcast_game_player_instances():
    engine = _create_engine()
    game_pk = 900000531

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitcher=None,
                inning_topbot="Bot",
            )

            result = get_statcast_game_players(connection)

            assert len(result) == 1
            game_player = result[0]
            assert isinstance(game_player, StatcastGamePlayer)
            assert isinstance(game_player.mlb_game_pk, int)
            assert isinstance(game_player.player_id, int)
            assert isinstance(game_player.team_code, str)
            assert game_player == StatcastGamePlayer(
                mlb_game_pk=game_pk,
                player_id=1001,
                team_code="NYY",
            )
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000541,
                batter=1001,
                pitcher=2002,
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            get_statcast_game_players(connection)

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
