"""Unit tests for curated plate-appearance-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.plate_appearance_data import PlateAppearanceLoadResult
from app.curated.plate_appearance_loader import (
    PlateAppearanceLoadOrchestrationResult,
    load_plate_appearances_from_statcast,
)
from app.curated.statcast_plate_appearance_data import StatcastPlateAppearance


def _plate_appearance(
    mlb_game_pk: int,
    at_bat_number: int,
) -> StatcastPlateAppearance:
    return StatcastPlateAppearance(
        mlb_game_pk=mlb_game_pk,
        at_bat_number=at_bat_number,
        batter_id=888009201,
        pitcher_id=888009202,
        batter_team_code="NYY",
        pitcher_team_code="BOS",
        inning=1,
        inning_topbot="Top",
        outcome_code="single",
    )


def test_empty_statcast_result_loads_nothing():
    connection = MagicMock()
    load_result = PlateAppearanceLoadResult(
        plate_appearances_supplied=0,
        plate_appearances_loaded=0,
    )

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            return_value=[],
        ) as mock_get,
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_plate_appearances_from_statcast(connection)

    mock_get.assert_called_once_with(connection)
    mock_load.assert_called_once_with(connection, [])
    assert result == PlateAppearanceLoadOrchestrationResult(
        plate_appearances_found=0,
        plate_appearances_loaded=0,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_extracted_plate_appearances_are_loaded():
    connection = MagicMock()
    plate_appearances = [
        _plate_appearance(900000921, 1),
        _plate_appearance(900000922, 2),
    ]
    load_result = PlateAppearanceLoadResult(
        plate_appearances_supplied=2,
        plate_appearances_loaded=2,
    )

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            return_value=plate_appearances,
        ) as mock_get,
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_plate_appearances_from_statcast(connection)

    mock_get.assert_called_once_with(connection)
    mock_load.assert_called_once_with(connection, plate_appearances)
    assert result == PlateAppearanceLoadOrchestrationResult(
        plate_appearances_found=2,
        plate_appearances_loaded=2,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_persistence_result_is_propagated():
    connection = MagicMock()
    plate_appearances = [
        _plate_appearance(900000923, 1),
        _plate_appearance(900000924, 1),
    ]
    load_result = PlateAppearanceLoadResult(
        plate_appearances_supplied=2,
        plate_appearances_loaded=1,
    )

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            return_value=plate_appearances,
        ),
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances",
            return_value=load_result,
        ),
    ):
        result = load_plate_appearances_from_statcast(connection)

    assert result == PlateAppearanceLoadOrchestrationResult(
        plate_appearances_found=2,
        plate_appearances_loaded=1,
    )


def test_extraction_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            side_effect=ValueError("conflicting plate appearance"),
        ),
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances"
        ) as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting plate appearance"):
            load_plate_appearances_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_persistence_errors_propagate():
    connection = MagicMock()
    plate_appearances = [_plate_appearance(900000925, 1)]

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            return_value=plate_appearances,
        ),
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances",
            side_effect=ValueError("missing game"),
        ),
    ):
        with pytest.raises(ValueError, match="missing game"):
            load_plate_appearances_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_orchestration_does_not_manage_transactions():
    connection = MagicMock()
    load_result = PlateAppearanceLoadResult(
        plate_appearances_supplied=0,
        plate_appearances_loaded=0,
    )

    with (
        patch(
            "app.curated.plate_appearance_loader.get_statcast_plate_appearances",
            return_value=[],
        ),
        patch(
            "app.curated.plate_appearance_loader.load_plate_appearances",
            return_value=load_result,
        ),
    ):
        load_plate_appearances_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
