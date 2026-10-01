"""Unit tests for curated team-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.team_loader import load_teams_from_mlb_stats_api
from app.mlb.stats_api import MlbTeam


def test_fetched_teams_are_loaded_and_result_is_returned():
    connection = MagicMock()
    teams = [
        MlbTeam(code="NYY", name="New York Yankees"),
        MlbTeam(code="BOS", name="Boston Red Sox"),
    ]
    load_result = 2

    with (
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

    mock_fetch.assert_called_once_with()
    mock_load.assert_called_once_with(connection, teams)
    assert result == load_result
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_fetch_mlb_teams_errors_propagate():
    connection = MagicMock()

    with (
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
