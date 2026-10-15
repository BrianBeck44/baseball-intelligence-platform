from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.reference_data import (
    GAME_TYPES,
    OUTCOME_TYPES,
    PITCH_OUTCOME_TYPES,
    PITCH_TYPES,
    load_reference_data,
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


def _reference_counts(connection: Connection) -> dict[str, int]:
    return {
        table_name: int(
            connection.execute(
                text(f"SELECT COUNT(*) FROM curated.{table_name}")
            ).scalar_one()
        )
        for table_name in (
            "pitch_type",
            "pitch_outcome_type",
            "outcome_type",
            "game_type",
        )
    }


def test_reference_data_definitions_have_unique_codes():
    assert len({value.code for value in PITCH_TYPES}) == len(PITCH_TYPES)
    assert len({value.code for value in PITCH_OUTCOME_TYPES}) == len(
        PITCH_OUTCOME_TYPES
    )
    assert len({value.code for value in OUTCOME_TYPES}) == len(OUTCOME_TYPES)
    assert len({value.code for value in GAME_TYPES}) == len(GAME_TYPES)


def test_outcome_types_include_sac_fly_double_play_and_triple_play():
    names_by_code = {value.code: value.name for value in OUTCOME_TYPES}

    assert names_by_code["sac_fly_double_play"] == "Sacrifice Fly Double Play"
    assert names_by_code["triple_play"] == "Triple Play"


def test_pitch_types_include_ep_fa_kn_and_po():
    names_by_code = {value.code: value.name for value in PITCH_TYPES}

    assert names_by_code["EP"] == "Eephus"
    assert names_by_code["FA"] == "Other"
    assert names_by_code["KN"] == "Knuckleball"
    assert names_by_code["PO"] == "Pitchout"


def test_pitch_outcome_types_include_bunt_foul_tip_and_pitchout():
    names_by_code = {value.code: value.name for value in PITCH_OUTCOME_TYPES}

    assert names_by_code["bunt_foul_tip"] == "Bunt Foul Tip"
    assert names_by_code["pitchout"] == "Pitchout"


def test_load_reference_data_populates_all_lookup_tables():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            load_reference_data(connection)

            pitch_type_count = connection.execute(
                text("SELECT COUNT(*) FROM curated.pitch_type")
            ).scalar_one()

            pitch_outcome_type_count = connection.execute(
                text("SELECT COUNT(*) FROM curated.pitch_outcome_type")
            ).scalar_one()

            outcome_type_count = connection.execute(
                text("SELECT COUNT(*) FROM curated.outcome_type")
            ).scalar_one()

            assert pitch_type_count >= len(PITCH_TYPES)
            assert pitch_outcome_type_count >= len(PITCH_OUTCOME_TYPES)
            assert outcome_type_count >= len(OUTCOME_TYPES)

            loaded_pitch_types = connection.execute(
                text(
                    """
                    SELECT code, name
                    FROM curated.pitch_type
                    WHERE code IN ('EP', 'FA', 'KN', 'PO')
                    ORDER BY code
                    """
                )
            ).mappings().all()
            assert [
                (row["code"], row["name"]) for row in loaded_pitch_types
            ] == [
                ("EP", "Eephus"),
                ("FA", "Other"),
                ("KN", "Knuckleball"),
                ("PO", "Pitchout"),
            ]

            loaded_pitch_outcomes = connection.execute(
                text(
                    """
                    SELECT code, name
                    FROM curated.pitch_outcome_type
                    WHERE code IN ('bunt_foul_tip', 'pitchout')
                    ORDER BY code
                    """
                )
            ).mappings().all()
            assert [
                (row["code"], row["name"]) for row in loaded_pitch_outcomes
            ] == [
                ("bunt_foul_tip", "Bunt Foul Tip"),
                ("pitchout", "Pitchout"),
            ]
    finally:
        engine.dispose()


def test_load_reference_data_inserts_regular_season_game_type():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            load_reference_data(connection)

            game_type = connection.execute(
                text(
                    """
                    SELECT code, name
                    FROM curated.game_type
                    WHERE code = :code
                    """
                ),
                {"code": "R"},
            ).mappings().one()

            assert game_type["code"] == "R"
            assert game_type["name"] == "Regular Season"
    finally:
        engine.dispose()


def test_load_reference_data_is_idempotent():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            load_reference_data(connection)
            counts_after_first = _reference_counts(connection)

            load_reference_data(connection)
            counts_after_second = _reference_counts(connection)

            assert counts_after_second == counts_after_first
            assert counts_after_first["pitch_type"] >= len(PITCH_TYPES)
            assert counts_after_first["pitch_outcome_type"] >= len(
                PITCH_OUTCOME_TYPES
            )
            assert counts_after_first["outcome_type"] >= len(OUTCOME_TYPES)
    finally:
        engine.dispose()


def test_reference_data_tests_do_not_persist_reference_writes():
    engine = _create_engine()

    try:
        with engine.connect() as committed:
            before = _reference_counts(committed)
            sentinel_before = committed.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM curated.game_type
                    WHERE code = :code
                    """
                ),
                {"code": "ZRR"},
            ).scalar_one()

        with _isolated_connection(engine) as connection:
            load_reference_data(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO curated.game_type (code, name)
                    VALUES (:code, :name)
                    """
                ),
                {"code": "ZRR", "name": "Zeta Reference Rollback"},
            )
            assert (
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM curated.game_type
                        WHERE code = :code
                        """
                    ),
                    {"code": "ZRR"},
                ).scalar_one()
                == 1
            )

        with engine.connect() as committed:
            after = _reference_counts(committed)
            sentinel_after = committed.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM curated.game_type
                    WHERE code = :code
                    """
                ),
                {"code": "ZRR"},
            ).scalar_one()

        assert after == before
        assert sentinel_before == 0
        assert sentinel_after == 0
    finally:
        engine.dispose()
