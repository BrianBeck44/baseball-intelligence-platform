"""Unit tests for curated team-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.team_loader import load_teams_from_mlb_stats_api
from app.mlb.stats_api import MlbTeam


def test_no_team_codes_skips_api_and_loader():
    connection = MagicMock()

    with (
        patch(
            "app.curated.team_loader.get_statcast_team_codes",
            return_value=[],
        ) as mock_get_codes,
        patch(
            "app.curated.team_loader.get_statcast_game_years"
        ) as mock_get_years,
        patch("app.curated.team_loader.fetch_mlb_teams") as mock_fetch,
        patch("app.curated.team_loader.load_mlb_teams") as mock_load,
    ):
        result = load_teams_from_mlb_stats_api(connection)

    mock_get_codes.assert_called_once_with(connection)
    mock_get_years.assert_not_called()
    mock_fetch.assert_not_called()
    mock_load.assert_not_called()
    assert result == 0
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_extracted_team_codes_and_years_are_resolved_and_loaded():
    connection = MagicMock()
    team_codes = ["BOS", "NYY"]
    seasons = [2022]
    teams = [
        MlbTeam(code="BOS", name="Boston Red Sox"),
        MlbTeam(code="NYY", name="New York Yankees"),
    ]
    load_result = 2

    with (
        patch(
            "app.curated.team_loader.get_statcast_team_codes",
            return_value=team_codes,
        ) as mock_get_codes,
        patch(
            "app.curated.team_loader.get_statcast_game_years",
            return_value=seasons,
        ) as mock_get_years,
        patch(
            "app.curated.team_loader.fetch_mlb_teams",
            return_value=teams,
        ) as mock_fetch,
        patch(
            "app.curated.team_loader.load_mlb_teams",
            return_value=load_result,
        ) as mock_load,
    ):
        result = load_teams_from_mlb_stats_api(connection)

    mock_get_codes.assert_called_once_with(connection)
    mock_get_years.assert_called_once_with(connection)
    mock_fetch.assert_called_once_with(team_codes, seasons)
    mock_load.assert_called_once_with(connection, teams)
    assert result == load_result
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_fetch_mlb_teams_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.team_loader.get_statcast_team_codes",
            return_value=["NYY"],
        ),
        patch(
            "app.curated.team_loader.get_statcast_game_years",
            return_value=[2022],
        ),
        patch(
            "app.curated.team_loader.fetch_mlb_teams",
            side_effect=RuntimeError("mlb api failed"),
        ),
        patch("app.curated.team_loader.load_mlb_teams") as mock_load,
    ):
        with pytest.raises(RuntimeError, match="mlb api failed"):
            load_teams_from_mlb_stats_api(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_load_mlb_teams_errors_propagate():
    connection = MagicMock()
    teams = [MlbTeam(code="NYY", name="New York Yankees")]

    with (
        patch(
            "app.curated.team_loader.get_statcast_team_codes",
            return_value=["NYY"],
        ),
        patch(
            "app.curated.team_loader.get_statcast_game_years",
            return_value=[2022],
        ),
        patch(
            "app.curated.team_loader.fetch_mlb_teams",
            return_value=teams,
        ),
        patch(
            "app.curated.team_loader.load_mlb_teams",
            side_effect=RuntimeError("team upsert failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="team upsert failed"):
            load_teams_from_mlb_stats_api(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
