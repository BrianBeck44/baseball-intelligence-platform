from sqlalchemy import create_engine, text

from app.core.config import settings
from app.curated.reference_data import (
    OUTCOME_TYPES,
    PITCH_OUTCOME_TYPES,
    PITCH_TYPES,
    load_reference_data,
)


def _create_engine():
    return create_engine(settings.database_url)


def _clear_reference_data(connection):
    connection.execute(text("DELETE FROM curated.outcome_type"))
    connection.execute(text("DELETE FROM curated.pitch_outcome_type"))
    connection.execute(text("DELETE FROM curated.pitch_type"))


def test_reference_data_definitions_have_unique_codes():
    assert len({value.code for value in PITCH_TYPES}) == len(PITCH_TYPES)
    assert len({value.code for value in PITCH_OUTCOME_TYPES}) == len(
        PITCH_OUTCOME_TYPES
    )
    assert len({value.code for value in OUTCOME_TYPES}) == len(OUTCOME_TYPES)


def test_load_reference_data_populates_all_lookup_tables():
    engine = _create_engine()

    try:
        with engine.begin() as connection:
            _clear_reference_data(connection)

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

            assert pitch_type_count == len(PITCH_TYPES)
            assert pitch_outcome_type_count == len(PITCH_OUTCOME_TYPES)
            assert outcome_type_count == len(OUTCOME_TYPES)
    finally:
        engine.dispose()


def test_load_reference_data_is_idempotent():
    engine = _create_engine()

    try:
        with engine.begin() as connection:
            _clear_reference_data(connection)

            load_reference_data(connection)
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

            assert pitch_type_count == len(PITCH_TYPES)
            assert pitch_outcome_type_count == len(PITCH_OUTCOME_TYPES)
            assert outcome_type_count == len(OUTCOME_TYPES)
    finally:
        engine.dispose()