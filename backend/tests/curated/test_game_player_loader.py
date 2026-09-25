"""Unit tests for curated game-player-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.game_player_data import GamePlayerLoadResult
from app.curated.game_player_loader import load_game_players_from_statcast
from app.curated.statcast_game_player_data import StatcastGamePlayer


def test_extracted_game_players_are_loaded_and_result_is_returned():
    connection = MagicMock()
    game_players = [
        StatcastGamePlayer(
            mlb_game_pk=900000701,
            player_id=888006201,
            team_code="NYY",
        ),
        StatcastGamePlayer(
            mlb_game_pk=900000702,
            player_id=888006202,
            team_code="BOS",
        ),
    ]
    load_result = GamePlayerLoadResult(
        game_players_supplied=2,
        game_players_loaded=2,
    )

    with (
        patch(
            "app.curated.game_player_loader.get_statcast_game_players",
            return_value=game_players,
        ) as mock_get_game_players,
        patch(
            "app.curated.game_player_loader.load_game_players",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_game_players_from_statcast(connection)

    mock_get_game_players.assert_called_once_with(connection)
    mock_load.assert_called_once_with(connection, game_players)
    assert result is load_result
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_get_statcast_game_players_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.game_player_loader.get_statcast_game_players",
            side_effect=ValueError("conflicting game player"),
        ),
        patch("app.curated.game_player_loader.load_game_players") as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting game player"):
            load_game_players_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_load_game_players_errors_propagate():
    connection = MagicMock()
    game_players = [
        StatcastGamePlayer(
            mlb_game_pk=900000703,
            player_id=888006203,
            team_code="NYY",
        )
    ]

    with (
        patch(
            "app.curated.game_player_loader.get_statcast_game_players",
            return_value=game_players,
        ),
        patch(
            "app.curated.game_player_loader.load_game_players",
            side_effect=ValueError("missing player"),
        ),
    ):
        with pytest.raises(ValueError, match="missing player"):
            load_game_players_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
