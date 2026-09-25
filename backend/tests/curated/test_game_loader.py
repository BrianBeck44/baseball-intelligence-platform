"""Unit tests for curated game-loading orchestration."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.curated.game_data import GameLoadResult
from app.curated.game_loader import load_games_from_statcast
from app.curated.statcast_game_data import StatcastGame


def test_extracted_games_are_loaded_and_result_is_returned():
    connection = MagicMock()
    games = [
        StatcastGame(
            mlb_game_pk=900000201,
            official_game_date=date(2024, 4, 8),
            game_type="R",
        ),
        StatcastGame(
            mlb_game_pk=900000202,
            official_game_date=date(2024, 4, 9),
            game_type="R",
        ),
    ]
    load_result = GameLoadResult(games_supplied=2, games_loaded=2)

    with (
        patch(
            "app.curated.game_loader.get_statcast_games",
            return_value=games,
        ) as mock_get_games,
        patch(
            "app.curated.game_loader.load_games",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_games_from_statcast(connection)

    mock_get_games.assert_called_once_with(connection)
    mock_load.assert_called_once_with(connection, games)
    assert result is load_result
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_get_statcast_games_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.game_loader.get_statcast_games",
            side_effect=ValueError("conflicting game"),
        ),
        patch("app.curated.game_loader.load_games") as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting game"):
            load_games_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_load_games_errors_propagate():
    connection = MagicMock()
    games = [
        StatcastGame(
            mlb_game_pk=900000203,
            official_game_date=date(2024, 4, 8),
            game_type="R",
        )
    ]

    with (
        patch(
            "app.curated.game_loader.get_statcast_games",
            return_value=games,
        ),
        patch(
            "app.curated.game_loader.load_games",
            side_effect=ValueError("missing season"),
        ),
    ):
        with pytest.raises(ValueError, match="missing season"):
            load_games_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
