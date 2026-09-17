"""Unit tests for V1 Statcast chunk validation."""

from datetime import date, datetime

import numpy as np
import pandas as pd

from app.ingestion.validation import (
    DUPLICATE_SOURCE_KEY,
    INVALID_SOURCE_KEY,
    MISSING_REQUIRED_FIELD,
    to_json_safe,
    validate_statcast_chunk,
)


def valid_row(**overrides):
    row = {
        "game_pk": 661032,
        "at_bat_number": 1,
        "pitch_number": 1,
        "game_type": "R",
    }
    row.update(overrides)
    return row


def validate_rows(rows, starting_source_row_number=1):
    return validate_statcast_chunk(
        pd.DataFrame(rows),
        starting_source_row_number=starting_source_row_number,
    )


def test_regular_season_row_is_accepted():
    result = validate_rows([valid_row()])

    assert len(result.valid_rows) == 1
    assert result.valid_rows.iloc[0]["game_type"] == "R"
    assert result.rejections == []
    assert result.records_filtered == 0
    assert result.records_rejected == 0


def test_non_regular_season_row_is_filtered():
    result = validate_rows([valid_row(game_type="S")])

    assert result.records_filtered == 1
    assert result.records_rejected == 0
    assert result.rejections == []
    assert result.valid_rows.empty


def test_missing_game_type_is_rejected_as_missing_required_field():
    result = validate_rows([valid_row(game_type=None)])

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == MISSING_REQUIRED_FIELD
    assert {"field": "game_type", "issue": "missing"} in rejection.details["errors"]
    assert result.valid_rows.empty
    assert result.records_filtered == 0


def test_missing_source_key_field_is_rejected_as_missing_required_field():
    result = validate_rows([valid_row(game_pk=None)])

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == MISSING_REQUIRED_FIELD
    assert {"field": "game_pk", "issue": "missing"} in rejection.details["errors"]
    assert result.valid_rows.empty


def test_invalid_source_key_value_is_rejected():
    result = validate_rows([valid_row(pitch_number=0)])

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == INVALID_SOURCE_KEY
    assert {
        "field": "pitch_number",
        "issue": "not_positive",
        "value": 0,
    } in rejection.details["errors"]
    assert result.valid_rows.empty


def test_non_integer_source_key_value_is_rejected():
    result = validate_rows([valid_row(at_bat_number="first")])

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == INVALID_SOURCE_KEY
    assert rejection.details["errors"][0]["field"] == "at_bat_number"
    assert rejection.details["errors"][0]["issue"] == "not_integer_compatible"


def test_duplicate_source_key_keeps_first_and_rejects_subsequent():
    result = validate_rows(
        [
            valid_row(pitch_number=1),
            valid_row(pitch_number=1),
            valid_row(pitch_number=2),
        ]
    )

    assert len(result.valid_rows) == 2
    assert list(result.valid_rows["pitch_number"]) == [1, 2]
    assert result.records_rejected == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == DUPLICATE_SOURCE_KEY
    assert rejection.source_row_number == 2
    assert rejection.details["errors"][0]["issue"] == "duplicate_source_key"
    assert rejection.details["errors"][0]["first_source_row_number"] == 1


def test_multiple_validation_problems_produce_one_rejection_record():
    result = validate_rows(
        [valid_row(game_pk=None, pitch_number=-1)]
    )

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    issues_by_field = {
        error["field"]: error["issue"] for error in rejection.details["errors"]
    }
    assert issues_by_field["game_pk"] == "missing"
    assert issues_by_field["pitch_number"] == "not_positive"
    assert rejection.raw_row["game_type"] == "R"


def test_missing_required_field_has_priority_over_invalid_source_key():
    result = validate_rows(
        [valid_row(game_pk=None, pitch_number=0)]
    )

    assert len(result.rejections) == 1
    rejection = result.rejections[0]
    assert rejection.rejection_reason == MISSING_REQUIRED_FIELD
    assert any(error["issue"] == "missing" for error in rejection.details["errors"])
    assert any(error["issue"] == "not_positive" for error in rejection.details["errors"])


def test_missing_required_field_has_priority_over_duplicate_source_key():
    result = validate_rows(
        [
            valid_row(),
            valid_row(game_type=None),
        ]
    )

    assert len(result.valid_rows) == 1
    assert len(result.rejections) == 1
    assert result.rejections[0].rejection_reason == MISSING_REQUIRED_FIELD
    assert result.rejections[0].source_row_number == 2


def test_invalid_source_key_has_priority_over_duplicate_source_key():
    result = validate_rows(
        [
            valid_row(pitch_number=0),
            valid_row(pitch_number=0),
        ]
    )

    assert result.valid_rows.empty
    assert result.records_rejected == 2
    assert all(
        rejection.rejection_reason == INVALID_SOURCE_KEY
        for rejection in result.rejections
    )


def test_source_row_number_is_one_based_for_first_chunk():
    result = validate_rows(
        [valid_row(game_type=None), valid_row(pitch_number=0)],
        starting_source_row_number=1,
    )

    assert result.rejections[0].source_row_number == 1
    assert result.rejections[1].source_row_number == 2


def test_source_row_number_incorporates_starting_source_row_number():
    result = validate_rows(
        [valid_row(game_type=None), valid_row(pitch_number=0)],
        starting_source_row_number=10001,
    )

    assert result.rejections[0].source_row_number == 10001
    assert result.rejections[1].source_row_number == 10002


def test_validation_counts_for_mixed_chunk():
    result = validate_rows(
        [
            valid_row(pitch_number=1),
            valid_row(game_type="S"),
            valid_row(game_pk=None),
            valid_row(pitch_number=2),
        ]
    )

    assert result.records_received == 4
    assert result.records_filtered == 1
    assert result.records_rejected == 1
    assert len(result.rejections) == result.records_rejected
    assert len(result.valid_rows) == 2
    assert list(result.valid_rows["pitch_number"]) == [1, 2]


def test_empty_chunk_returns_zero_counts():
    result = validate_statcast_chunk(pd.DataFrame(), starting_source_row_number=1)

    assert result.records_received == 0
    assert result.records_filtered == 0
    assert result.records_rejected == 0
    assert result.valid_rows.empty
    assert result.rejections == []


def test_to_json_safe_numpy_integer_scalar():
    assert to_json_safe(np.int64(661032)) == 661032


def test_to_json_safe_numpy_float_scalar():
    assert to_json_safe(np.float64(94.2)) == 94.2


def test_to_json_safe_missing_values():
    assert to_json_safe(None) is None
    assert to_json_safe(np.nan) is None
    assert to_json_safe(pd.NA) is None
    assert to_json_safe(pd.NaT) is None
    assert to_json_safe(np.datetime64("NaT")) is None


def test_to_json_safe_datetime_and_date():
    assert to_json_safe(datetime(2022, 4, 7, 12, 30, 0)) == "2022-04-07T12:30:00"
    assert to_json_safe(date(2022, 4, 7)) == "2022-04-07"
    assert to_json_safe(pd.Timestamp("2022-04-07T12:30:00")) == "2022-04-07T12:30:00"
    assert to_json_safe(np.datetime64("2022-04-07")) == "2022-04-07T00:00:00"


def test_to_json_safe_nan_and_infinity():
    assert to_json_safe(float("nan")) is None
    assert to_json_safe(float("inf")) is None
    assert to_json_safe(float("-inf")) is None
    assert to_json_safe(np.inf) is None
    assert to_json_safe(-np.inf) is None
