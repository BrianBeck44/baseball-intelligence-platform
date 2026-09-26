"""Tests for distinct plate-appearance extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_plate_appearance_data import (
    StatcastPlateAppearance,
    get_statcast_plate_appearances,
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
    at_bat_number: int = 1,
    pitch_number: int = 1,
    batter: int | None = 1001,
    pitcher: int | None = 2002,
    home_team: str | None = "NYY",
    away_team: str | None = "BOS",
    inning: int | None = 1,
    inning_topbot: str | None = "Top",
    events: str | None = None,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=(
            "pytest_statcast_plate_appearance_data_"
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
                inning,
                inning_topbot,
                events
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
                :inning,
                :inning_topbot,
                :events
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
            "inning": inning,
            "inning_topbot": inning_topbot,
            "events": events,
        },
    )


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_plate_appearances(connection) == []
    finally:
        engine.dispose()


def test_single_plate_appearance_is_extracted():
    engine = _create_engine()
    game_pk = 900000801

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                events="single",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="single",
                )
            ]
    finally:
        engine.dispose()


def test_multiple_pitches_in_one_plate_appearance_produce_one_result():
    engine = _create_engine()
    game_pk = 900000802

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=2,
                events="strikeout",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="strikeout",
                )
            ]
    finally:
        engine.dispose()


def test_multiple_plate_appearances_are_extracted():
    engine = _create_engine()
    game_pk = 900000803

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                at_bat_number=1,
                events="walk",
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                at_bat_number=2,
                batter=3003,
                events="home_run",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="walk",
                ),
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=2,
                    batter_id=3003,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="home_run",
                ),
            ]
    finally:
        engine.dispose()


def test_multiple_games_are_extracted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000804,
                events="single",
            )
            _insert_pitch(
                connection,
                game_pk=900000805,
                home_team="LAD",
                away_team="SF",
                events="double",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=900000804,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="single",
                ),
                StatcastPlateAppearance(
                    mlb_game_pk=900000805,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="SF",
                    pitcher_team_code="LAD",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="double",
                ),
            ]
    finally:
        engine.dispose()


def test_top_assigns_away_batter_and_home_pitcher():
    engine = _create_engine()
    game_pk = 900000806

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning_topbot="Top",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code=None,
                )
            ]
    finally:
        engine.dispose()


def test_bot_assigns_home_batter_and_away_pitcher():
    engine = _create_engine()
    game_pk = 900000807

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning_topbot="Bot",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="NYY",
                    pitcher_team_code="BOS",
                    inning=1,
                    inning_topbot="Bot",
                    outcome_code=None,
                )
            ]
    finally:
        engine.dispose()


def test_null_events_produces_none_outcome_code():
    engine = _create_engine()
    game_pk = 900000808

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=game_pk, events=None)

            result = get_statcast_plate_appearances(connection)

            assert len(result) == 1
            assert result[0].outcome_code is None
    finally:
        engine.dispose()


def test_non_null_events_is_extracted():
    engine = _create_engine()
    game_pk = 900000809

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=game_pk, events="field_out")

            result = get_statcast_plate_appearances(connection)

            assert len(result) == 1
            assert result[0].outcome_code == "field_out"
    finally:
        engine.dispose()


def test_duplicate_identical_events_values_are_accepted():
    engine = _create_engine()
    game_pk = 900000810

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=1,
                events="single",
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=2,
                events="single",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=game_pk,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="single",
                )
            ]
    finally:
        engine.dispose()


def test_conflicting_events_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000811

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=1,
                events="single",
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitch_number=2,
                events="double",
            )

            with pytest.raises(ValueError, match=str(game_pk)):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_batter_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000861

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=1001,
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                batter=3003,
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"batter.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_pitcher_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000862

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitcher=2002,
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                pitcher=4004,
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"pitcher.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_home_team_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000863

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="TB",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"home_team.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_away_team_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000864

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                away_team="BOS",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                away_team="TB",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"away_team.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_inning_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000865

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning=1,
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning=2,
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"inning.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_conflicting_inning_topbot_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000866

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning_topbot="Top",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                inning_topbot="Bot",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=rf"inning_topbot.*game_pk={game_pk}"):
                get_statcast_plate_appearances(connection)
    finally:
        engine.dispose()


def test_incomplete_rows_are_excluded():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000812,
                batter=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000813,
                pitcher=None,
                at_bat_number=2,
            )
            _insert_pitch(
                connection,
                game_pk=900000814,
                home_team=None,
                at_bat_number=3,
            )
            _insert_pitch(
                connection,
                game_pk=900000815,
                away_team=None,
                at_bat_number=4,
            )
            _insert_pitch(
                connection,
                game_pk=900000816,
                inning=None,
                at_bat_number=5,
            )
            _insert_pitch(
                connection,
                game_pk=900000817,
                events="walk",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=900000817,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="BOS",
                    pitcher_team_code="NYY",
                    inning=1,
                    inning_topbot="Top",
                    outcome_code="walk",
                )
            ]
    finally:
        engine.dispose()


def test_invalid_inning_topbot_is_excluded():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000818,
                inning_topbot="TOP",
            )
            _insert_pitch(
                connection,
                game_pk=900000819,
                inning_topbot="Mid",
            )
            _insert_pitch(
                connection,
                game_pk=900000820,
                inning_topbot=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000821,
                inning_topbot="Bot",
                events="single",
            )

            result = get_statcast_plate_appearances(connection)

            assert result == [
                StatcastPlateAppearance(
                    mlb_game_pk=900000821,
                    at_bat_number=1,
                    batter_id=1001,
                    pitcher_id=2002,
                    batter_team_code="NYY",
                    pitcher_team_code="BOS",
                    inning=1,
                    inning_topbot="Bot",
                    outcome_code="single",
                )
            ]
    finally:
        engine.dispose()


def test_results_are_ordered_by_game_pk_and_at_bat_number():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000833,
                at_bat_number=2,
            )
            _insert_pitch(
                connection,
                game_pk=900000831,
                at_bat_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=900000833,
                at_bat_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=900000832,
                at_bat_number=1,
            )

            result = get_statcast_plate_appearances(connection)

            assert [
                (pa.mlb_game_pk, pa.at_bat_number) for pa in result
            ] == [
                (900000831, 1),
                (900000832, 1),
                (900000833, 1),
                (900000833, 2),
            ]
    finally:
        engine.dispose()


def test_returned_values_are_statcast_plate_appearance_instances():
    engine = _create_engine()
    game_pk = 900000841

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                events="single",
            )

            result = get_statcast_plate_appearances(connection)

            assert len(result) == 1
            plate_appearance = result[0]
            assert isinstance(plate_appearance, StatcastPlateAppearance)
            assert isinstance(plate_appearance.mlb_game_pk, int)
            assert isinstance(plate_appearance.at_bat_number, int)
            assert isinstance(plate_appearance.batter_id, int)
            assert isinstance(plate_appearance.pitcher_id, int)
            assert isinstance(plate_appearance.batter_team_code, str)
            assert isinstance(plate_appearance.pitcher_team_code, str)
            assert isinstance(plate_appearance.inning, int)
            assert isinstance(plate_appearance.inning_topbot, str)
            assert isinstance(plate_appearance.outcome_code, str)
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=900000851)
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            get_statcast_plate_appearances(connection)

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
