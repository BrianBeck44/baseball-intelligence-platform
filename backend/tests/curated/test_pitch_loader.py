"""Unit tests for curated pitch-loading orchestration."""

from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

from app.curated.pitch_data import CuratedPitch
from app.curated.pitch_loader import (
    PitchLoadOrchestrationResult,
    load_pitches_from_statcast,
)
from app.curated.statcast_pitch_data import StatcastPitch


def _statcast_pitch(
    mlb_game_pk: int,
    at_bat_number: int,
    pitch_number: int,
) -> StatcastPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(StatcastPitch)
        if field.name not in {"mlb_game_pk", "at_bat_number", "pitch_number"}
    }
    return StatcastPitch(
        mlb_game_pk=mlb_game_pk,
        at_bat_number=at_bat_number,
        pitch_number=pitch_number,
        **values,  # type: ignore[arg-type]
    )


def _curated_pitch(
    plate_appearance_id: int,
    pitch_number: int,
) -> CuratedPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(CuratedPitch)
        if field.name not in {"plate_appearance_id", "pitch_number"}
    }
    return CuratedPitch(
        plate_appearance_id=plate_appearance_id,
        pitch_number=pitch_number,
        **values,  # type: ignore[arg-type]
    )


def test_empty_statcast_result_loads_nothing():
    connection = MagicMock()

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=[],
        ) as mock_get,
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=[],
        ) as mock_transform,
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=0,
        ) as mock_load,
    ):
        result = load_pitches_from_statcast(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, [])
    mock_load.assert_called_once_with(connection, [])
    assert result == PitchLoadOrchestrationResult(
        pitches_found=0,
        pitches_loaded=0,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_extracted_pitches_are_loaded():
    connection = MagicMock()
    pitches = [
        _statcast_pitch(900007001, 1, 1),
        _statcast_pitch(900007002, 2, 1),
    ]
    curated_pitches = [
        _curated_pitch(101, 1),
        _curated_pitch(102, 1),
    ]

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=pitches,
        ) as mock_get,
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ) as mock_transform,
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=2,
        ) as mock_load,
    ):
        result = load_pitches_from_statcast(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, pitches)
    mock_load.assert_called_once_with(connection, curated_pitches)
    assert result == PitchLoadOrchestrationResult(
        pitches_found=2,
        pitches_loaded=2,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_persistence_result_is_propagated():
    connection = MagicMock()
    pitches = [
        _statcast_pitch(900007003, 1, 1),
        _statcast_pitch(900007004, 1, 2),
    ]
    curated_pitches = [
        _curated_pitch(201, 1),
        _curated_pitch(201, 2),
    ]

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=pitches,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=42,
        ),
    ):
        result = load_pitches_from_statcast(connection)

    assert result == PitchLoadOrchestrationResult(
        pitches_found=2,
        pitches_loaded=42,
    )


def test_extraction_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            side_effect=ValueError("conflicting pitch"),
        ),
        patch("app.curated.pitch_loader.transform_pitches") as mock_transform,
        patch("app.curated.pitch_loader.load_pitches") as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting pitch"):
            load_pitches_from_statcast(connection)

    mock_transform.assert_not_called()
    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_transformation_errors_propagate():
    connection = MagicMock()
    pitches = [_statcast_pitch(900007005, 1, 1)]

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=pitches,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            side_effect=ValueError("missing game"),
        ),
        patch("app.curated.pitch_loader.load_pitches") as mock_load,
    ):
        with pytest.raises(ValueError, match="missing game"):
            load_pitches_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_persistence_errors_propagate():
    connection = MagicMock()
    pitches = [_statcast_pitch(900007006, 1, 1)]
    curated_pitches = [_curated_pitch(301, 1)]

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=pitches,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            side_effect=ValueError("insert failed"),
        ),
    ):
        with pytest.raises(ValueError, match="insert failed"):
            load_pitches_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_orchestration_does_not_manage_transactions():
    connection = MagicMock()

    with (
        patch(
            "app.curated.pitch_loader.get_statcast_pitches",
            return_value=[],
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=[],
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=0,
        ),
    ):
        load_pitches_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
