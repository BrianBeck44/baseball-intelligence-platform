"""Unit tests for curated game-team-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.game_team_data import GameTeamLoadResult
from app.curated.game_team_loader import load_game_teams_from_statcast
from app.curated.statcast_game_team_data import StatcastGameTeam


def test_extracted_game_teams_are_loaded_and_result_is_returned():
    connection = MagicMock()
    game_teams = [
        StatcastGameTeam(
            mlb_game_pk=900000801,
            team_code="NYY",
            home_away="home",
        ),
        StatcastGameTeam(
            mlb_game_pk=900000802,
            team_code="BOS",
            home_away="away",
        ),
    ]
    load_result = GameTeamLoadResult(
        game_teams_supplied=2,
        game_teams_loaded=2,
    )

    with (
        patch(
            "app.curated.game_team_loader.get_statcast_game_teams",
            return_value=game_teams,
        ) as mock_get_game_teams,
        patch(
            "app.curated.game_team_loader.load_game_teams",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_game_teams_from_statcast(connection)

    mock_get_game_teams.assert_called_once_with(connection)
    mock_load.assert_called_once_with(connection, game_teams)
    assert result is load_result
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_get_statcast_game_teams_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.game_team_loader.get_statcast_game_teams",
            side_effect=ValueError("conflicting game team"),
        ),
        patch("app.curated.game_team_loader.load_game_teams") as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting game team"):
            load_game_teams_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_load_game_teams_errors_propagate():
    connection = MagicMock()
    game_teams = [
        StatcastGameTeam(
            mlb_game_pk=900000803,
            team_code="NYY",
            home_away="home",
        )
    ]

    with (
        patch(
            "app.curated.game_team_loader.get_statcast_game_teams",
            return_value=game_teams,
        ),
        patch(
            "app.curated.game_team_loader.load_game_teams",
            side_effect=ValueError("missing team"),
        ),
    ):
        with pytest.raises(ValueError, match="missing team"):
            load_game_teams_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
