"""Unit tests for analytics player-game batting orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.analytics.player_game_batting_data import (
    PlayerGameBatting,
    PlayerGameBattingAppearance,
)
from app.analytics.player_game_batting_loader import (
    PlayerGameBattingLoadResult,
    load_player_game_batting_from_curated,
)


def _appearance(
    *,
    player_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
    outcome_code: str | None = "single",
) -> PlayerGameBattingAppearance:
    return PlayerGameBattingAppearance(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        outcome_code=outcome_code,
    )


def _row(
    *,
    player_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
) -> PlayerGameBatting:
    return PlayerGameBatting(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
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
    )


def test_normal_pipeline_coordinates_extract_transform_load():
    connection = MagicMock()
    appearances = [
        _appearance(player_id=1, game_id=10, team_id=100),
        _appearance(player_id=1, game_id=10, team_id=100, outcome_code="walk"),
        _appearance(player_id=2, game_id=11, team_id=200),
    ]
    rows = [
        _row(player_id=1, game_id=10, team_id=100),
        _row(player_id=2, game_id=11, team_id=200),
    ]

    with (
        patch(
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            return_value=appearances,
        ) as mock_get,
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting",
            return_value=rows,
        ) as mock_transform,
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting",
            return_value=2,
        ) as mock_load,
    ):
        result = load_player_game_batting_from_curated(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, appearances)
    mock_load.assert_called_once_with(connection, rows)
    assert result == PlayerGameBattingLoadResult(
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
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            return_value=[],
        ) as mock_get,
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting",
            return_value=[],
        ) as mock_transform,
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting",
            return_value=0,
        ) as mock_load,
    ):
        result = load_player_game_batting_from_curated(connection)

    mock_get.assert_called_once_with(connection)
    mock_transform.assert_called_once_with(connection, [])
    mock_load.assert_called_once_with(connection, [])
    assert result == PlayerGameBattingLoadResult(
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
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            side_effect=ValueError("extract failed"),
        ),
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting"
        ) as mock_transform,
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting"
        ) as mock_load,
    ):
        with pytest.raises(ValueError, match="extract failed"):
            load_player_game_batting_from_curated(connection)

    mock_transform.assert_not_called()
    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_transformation_errors_propagate():
    connection = MagicMock()
    appearances = [_appearance()]

    with (
        patch(
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            return_value=appearances,
        ),
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting",
            side_effect=ValueError("unknown outcome"),
        ),
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting"
        ) as mock_load,
    ):
        with pytest.raises(ValueError, match="unknown outcome"):
            load_player_game_batting_from_curated(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_errors_propagate():
    connection = MagicMock()
    appearances = [_appearance()]
    rows = [_row()]

    with (
        patch(
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            return_value=appearances,
        ),
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting",
            return_value=rows,
        ),
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting",
            side_effect=ValueError("insert failed"),
        ),
    ):
        with pytest.raises(ValueError, match="insert failed"):
            load_player_game_batting_from_curated(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_orchestrator_does_not_manage_transactions():
    connection = MagicMock()

    with (
        patch(
            "app.analytics.player_game_batting_loader.get_player_game_batting_appearances",
            return_value=[],
        ),
        patch(
            "app.analytics.player_game_batting_loader.transform_player_game_batting",
            return_value=[],
        ),
        patch(
            "app.analytics.player_game_batting_loader.load_player_game_batting",
            return_value=0,
        ),
    ):
        load_player_game_batting_from_curated(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
