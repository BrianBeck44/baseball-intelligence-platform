"""Rollback-only CA-OPS pipeline validation against the test database."""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.load_all import SeasonLoadResult
from app.analytics.player_season_batting_data import PlayerSeasonBatting
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.analytics.player_season_ca_ops_data import (
    get_player_season_ca_ops_appearances,
    get_player_season_ca_ops_targets,
    transform_player_season_ca_ops,
)
from app.analytics.player_season_ca_ops_loader import load_player_season_ca_ops
from app.analytics.rebuild_validation import validate_player_season_ca_ops_load
from tests.db import REQUIRED_TEST_DATABASE_NAME, create_test_engine


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


def _snapshot(connection):
    return connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(plate_appearances), 0) AS plate_appearances,
                COUNT(*) FILTER (WHERE ca_ops IS NULL) AS null_ca_ops_rows
            FROM analytics.player_season_ca_ops
            """
        )
    ).mappings().one()


def _insert_id(connection: Connection, sql: str, params: dict) -> int:
    return connection.execute(text(sql), params).scalar_one()


def _outcome_id(connection: Connection, code: str) -> int:
    existing = connection.execute(
        text("SELECT id FROM curated.outcome_type WHERE code = :code"),
        {"code": code},
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing)
    return _insert_id(
        connection,
        """
        INSERT INTO curated.outcome_type (code, name)
        VALUES (:code, :name)
        RETURNING id
        """,
        {"code": code, "name": code},
    )


def _seed_reconciliation_rows(connection: Connection) -> dict[str, int]:
    season_id = _insert_id(
        connection,
        "INSERT INTO curated.season (season_year) VALUES (:year) RETURNING season_id",
        {"year": 2637},
    )
    game_type_id = _insert_id(
        connection,
        """
        INSERT INTO curated.game_type (code, name)
        VALUES (:code, :name)
        RETURNING id
        """,
        {"code": "ZCV", "name": "Zeta CA-OPS Validation"},
    )
    game_id = _insert_id(
        connection,
        """
        INSERT INTO curated.game (
            mlb_game_pk, season_id, official_game_date, game_type_id
        )
        VALUES (:mlb_game_pk, :season_id, :official_game_date, :game_type_id)
        RETURNING game_id
        """,
        {
            "mlb_game_pk": 919003101,
            "season_id": season_id,
            "official_game_date": date(2637, 4, 8),
            "game_type_id": game_type_id,
        },
    )
    batter_id = _insert_id(
        connection,
        """
        INSERT INTO curated.player (mlb_player_id, full_name)
        VALUES (:mlb_player_id, :full_name)
        RETURNING player_id
        """,
        {"mlb_player_id": 888093301, "full_name": "CA Validation Batter"},
    )
    other_batter_id = _insert_id(
        connection,
        """
        INSERT INTO curated.player (mlb_player_id, full_name)
        VALUES (:mlb_player_id, :full_name)
        RETURNING player_id
        """,
        {"mlb_player_id": 888093302, "full_name": "CA Validation Other"},
    )
    pitcher_id = _insert_id(
        connection,
        """
        INSERT INTO curated.player (mlb_player_id, full_name)
        VALUES (:mlb_player_id, :full_name)
        RETURNING player_id
        """,
        {"mlb_player_id": 888093303, "full_name": "CA Validation Pitcher"},
    )
    batter_team_id = _insert_id(
        connection,
        "INSERT INTO curated.team (code, name) VALUES (:code, :name) RETURNING team_id",
        {"code": "ZCV", "name": "Zeta CA Validation"},
    )
    pitcher_team_id = _insert_id(
        connection,
        "INSERT INTO curated.team (code, name) VALUES (:code, :name) RETURNING team_id",
        {"code": "ZCW", "name": "Zeta CA West"},
    )
    single_id = _outcome_id(connection, "single")
    out_id = _outcome_id(connection, "field_out")
    for at_bat_number, batter, outcome_id in (
        (1, batter_id, single_id),
        (2, other_batter_id, out_id),
        (3, other_batter_id, single_id),
    ):
        connection.execute(
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
                    outcome_type_id,
                    stand,
                    p_throws
                )
                VALUES (
                    :game_id,
                    :at_bat_number,
                    :batter_id,
                    :pitcher_id,
                    :batter_team_id,
                    :pitcher_team_id,
                    1,
                    'Top',
                    :outcome_type_id,
                    'L',
                    'R'
                )
                """
            ),
            {
                "game_id": game_id,
                "at_bat_number": at_bat_number,
                "batter_id": batter,
                "pitcher_id": pitcher_id,
                "batter_team_id": batter_team_id,
                "pitcher_team_id": pitcher_team_id,
                "outcome_type_id": outcome_id,
            },
        )
    load_player_season_batting(
        connection,
        [
            PlayerSeasonBatting(
                player_id=batter_id,
                season_id=season_id,
                games=1,
                plate_appearances=1,
                at_bats=1,
                hits=1,
                singles=1,
                doubles=0,
                triples=0,
                home_runs=0,
                walks=0,
                hit_by_pitch=0,
                strikeouts=0,
                sacrifice_flies=0,
                sacrifice_bunts=0,
                batting_average=1.0,
                on_base_percentage=1.0,
                slugging_percentage=1.0,
                ops=2.0,
                strikeout_rate=0.0,
                walk_rate=0.0,
            ),
            PlayerSeasonBatting(
                player_id=other_batter_id,
                season_id=season_id,
                games=1,
                plate_appearances=2,
                at_bats=2,
                hits=1,
                singles=1,
                doubles=0,
                triples=0,
                home_runs=0,
                walks=0,
                hit_by_pitch=0,
                strikeouts=0,
                sacrifice_flies=0,
                sacrifice_bunts=0,
                batting_average=0.5,
                on_base_percentage=0.5,
                slugging_percentage=0.5,
                ops=1.0,
                strikeout_rate=0.0,
                walk_rate=0.0,
            ),
        ],
    )
    return {
        "batter_id": batter_id,
        "other_batter_id": other_batter_id,
        "season_id": season_id,
    }


def test_ca_ops_pipeline_validation_uses_test_database_and_rolls_back():
    engine = _create_engine()

    try:
        with engine.connect() as probe:
            database_name = probe.execute(text("SELECT current_database()")).scalar_one()
            assert database_name == REQUIRED_TEST_DATABASE_NAME
            before = dict(_snapshot(probe))

        with _isolated_connection(engine) as connection:
            ids = _seed_reconciliation_rows(connection)
            appearances = get_player_season_ca_ops_appearances(connection)
            targets = get_player_season_ca_ops_targets(connection)
            rows = transform_player_season_ca_ops(
                connection,
                appearances,
                targets,
            )
            loaded_count = load_player_season_ca_ops(connection, rows)
            validate_player_season_ca_ops_load(
                connection,
                SeasonLoadResult(
                    extracted_count=len(appearances),
                    transformed_count=len(rows),
                    loaded_count=loaded_count,
                ),
            )
            stored = connection.execute(
                text(
                    """
                    SELECT player_id, observed_ops, league_ops, ca_ops
                    FROM analytics.player_season_ca_ops
                    WHERE season_id = :season_id
                    ORDER BY player_id
                    """
                ),
                {"season_id": ids["season_id"]},
            ).mappings().all()
            by_player = {int(row["player_id"]): row for row in stored}
            assert loaded_count == len(targets)
            assert len(by_player) == 2
            assert float(by_player[ids["batter_id"]]["observed_ops"]) == 2.0
            assert float(by_player[ids["other_batter_id"]]["observed_ops"]) == 1.0
            assert by_player[ids["batter_id"]]["ca_ops"] is not None
            assert by_player[ids["other_batter_id"]]["ca_ops"] is not None

        with engine.connect() as probe:
            after = dict(_snapshot(probe))
            assert after == before
            assert (
                probe.execute(text("SELECT current_database()")).scalar_one()
                == REQUIRED_TEST_DATABASE_NAME
            )
    finally:
        engine.dispose()


def test_validation_fails_when_persisted_ca_ops_is_corrupted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _seed_reconciliation_rows(connection)
            appearances = get_player_season_ca_ops_appearances(connection)
            targets = get_player_season_ca_ops_targets(connection)
            rows = transform_player_season_ca_ops(
                connection,
                appearances,
                targets,
            )
            loaded_count = load_player_season_ca_ops(connection, rows)
            result = SeasonLoadResult(
                extracted_count=len(appearances),
                transformed_count=len(rows),
                loaded_count=loaded_count,
            )
            validate_player_season_ca_ops_load(connection, result)

            connection.execute(
                text(
                    """
                    UPDATE analytics.player_season_ca_ops
                    SET ca_ops = COALESCE(ca_ops, 0) + 1
                    """
                )
            )

            with pytest.raises(ValueError, match="recomputed_mismatches"):
                validate_player_season_ca_ops_load(connection, result)
    finally:
        engine.dispose()


def test_validation_script_skips_empty_committed_season_batting(capsys):
    engine = _create_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            batting_rows = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM analytics.player_season_batting")
                ).scalar_one()
            )
            assert database_name == REQUIRED_TEST_DATABASE_NAME
        if batting_rows != 0:
            pytest.skip("committed season batting is populated")

        from scripts.validate_player_season_ca_ops_pipeline import main

        assert main() == 0
        output = capsys.readouterr().out
        assert f"database: {REQUIRED_TEST_DATABASE_NAME}" in output
        assert "populated-data reconciliation: skipped" in output
        assert "this is not formula validation" in output
        assert "Player Season CA-OPS pipeline validation succeeded." not in output
        assert "rollback: succeeded" in output
    finally:
        engine.dispose()


