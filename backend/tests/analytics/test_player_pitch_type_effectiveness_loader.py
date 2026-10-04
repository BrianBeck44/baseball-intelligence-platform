"""Unit tests for analytics pitch-type effectiveness orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.analytics.player_pitch_type_effectiveness_data import (
    PlayerPitchTypeEffectiveness,
    PlayerPitchTypeEffectivenessPitch,
)
from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
    load_player_pitch_type_effectiveness_from_curated,
)


def _pitch(
    *,
    player_id: int = 1,
    pitch_type_id: int = 10,
    plate_appearance_id: int = 100,
) -> PlayerPitchTypeEffectivenessPitch:
    return PlayerPitchTypeEffectivenessPitch(
        player_id=player_id,
        pitch_type_id=pitch_type_id,
        plate_appearance_id=plate_appearance_id,
        pitch_outcome_code="ball",
        pa_outcome_code=None,
        is_terminal_pitch=True,
    )


def _row(
    *,
    player_id: int = 1,
    pitch_type_id: int = 10,
) -> PlayerPitchTypeEffectiveness:
    return PlayerPitchTypeEffectiveness(
        player_id=player_id,
        pitch_type_id=pitch_type_id,
        pitches=1,
        plate_appearances=1,
        balls_in_play=0,
        swings=0,
        whiffs=0,
        called_strikes=0,
        fouls=0,
        hits_allowed=0,
        home_runs_allowed=0,
        strikeouts=0,
        walks=0,
        hit_by_pitch=0,
        whiff_rate=None,
        called_strike_rate=0.0,
        swing_rate=0.0,
        contact_rate=None,
        strikeout_rate=0.0,
    )


def test_normal_pipeline_coordinates_extract_transform_load():
    connection = MagicMock()
    pitches = [
        _pitch(player_id=1, pitch_type_id=10),
        _pitch(player_id=1, pitch_type_id=10, plate_appearance_id=101),
        _pitch(player_id=2, pitch_type_id=20),
    ]
    rows = [
        _row(player_id=1, pitch_type_id=10),
        _row(player_id=2, pitch_type_id=20),
    ]

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            return_value=pitches,
        ) as mock_get,
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness",
            return_value=rows,
        ) as mock_transform,
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness",
            return_value=2,
        ) as mock_load,
    ):
        result = load_player_pitch_type_effectiveness_from_curated(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, pitches)
    mock_load.assert_called_once_with(connection, rows)
    assert result == PlayerPitchTypeEffectivenessLoadResult(
        extracted_count=3,
        transformed_count=2,
        loaded_count=2,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_empty_extraction_completes_with_zero_counts():
    connection = MagicMock()

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            return_value=[],
        ) as mock_get,
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness",
            return_value=[],
        ) as mock_transform,
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness",
            return_value=0,
        ) as mock_load,
    ):
        result = load_player_pitch_type_effectiveness_from_curated(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, [])
    mock_load.assert_called_once_with(connection, [])
    assert result == PlayerPitchTypeEffectivenessLoadResult(
        extracted_count=0,
        transformed_count=0,
        loaded_count=0,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_extraction_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            side_effect=ValueError("extract failed"),
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness"
        ) as mock_transform,
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness"
        ) as mock_load,
    ):
        with pytest.raises(ValueError, match="extract failed"):
            load_player_pitch_type_effectiveness_from_curated(connection)

    mock_transform.assert_not_called()
    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_transformation_errors_propagate():
    connection = MagicMock()
    pitches = [_pitch()]

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            return_value=pitches,
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness",
            side_effect=ValueError("unknown outcome"),
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness"
        ) as mock_load,
    ):
        with pytest.raises(ValueError, match="unknown outcome"):
            load_player_pitch_type_effectiveness_from_curated(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_errors_propagate():
    connection = MagicMock()
    pitches = [_pitch()]
    rows = [_row()]

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            return_value=pitches,
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness",
            return_value=rows,
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness",
            side_effect=ValueError("insert failed"),
        ),
    ):
        with pytest.raises(ValueError, match="insert failed"):
            load_player_pitch_type_effectiveness_from_curated(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_orchestrator_does_not_manage_transactions():
    connection = MagicMock()

    with (
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "get_player_pitch_type_effectiveness_pitches",
            return_value=[],
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "transform_player_pitch_type_effectiveness",
            return_value=[],
        ),
        patch(
            "app.analytics.player_pitch_type_effectiveness_loader."
            "load_player_pitch_type_effectiveness",
            return_value=0,
        ),
    ):
        load_player_pitch_type_effectiveness_from_curated(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
