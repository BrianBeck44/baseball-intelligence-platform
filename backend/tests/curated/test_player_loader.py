"""Unit tests for curated player-loading orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from app.curated.player_loader import PlayerLoadResult, load_players_from_statcast
from app.mlb.stats_api import MlbPlayer


def test_no_player_ids_skips_api_and_loader():
    connection = MagicMock()

    with (
        patch(
            "app.curated.player_loader.get_statcast_player_ids",
            return_value=[],
        ) as mock_get_ids,
        patch("app.curated.player_loader.fetch_mlb_players") as mock_fetch,
        patch("app.curated.player_loader.load_mlb_players") as mock_load,
    ):
        result = load_players_from_statcast(connection)

    mock_get_ids.assert_called_once_with(connection)
    mock_fetch.assert_not_called()
    mock_load.assert_not_called()
    assert result == PlayerLoadResult(
        player_ids_found=0,
        players_resolved=0,
        players_loaded=0,
    )


def test_found_players_are_resolved_and_loaded():
    connection = MagicMock()
    player_ids = [1001, 1002]
    players = [
        MlbPlayer(mlb_player_id=1001, full_name="Ada Batter"),
        MlbPlayer(mlb_player_id=1002, full_name="Pat Pitcher"),
    ]

    with (
        patch(
            "app.curated.player_loader.get_statcast_player_ids",
            return_value=player_ids,
        ) as mock_get_ids,
        patch(
            "app.curated.player_loader.fetch_mlb_players",
            return_value=players,
        ) as mock_fetch,
        patch(
            "app.curated.player_loader.load_mlb_players",
            return_value=2,
        ) as mock_load,
    ):
        result = load_players_from_statcast(connection)

    mock_get_ids.assert_called_once_with(connection)
    mock_fetch.assert_called_once_with(player_ids)
    mock_load.assert_called_once_with(connection, players)
    assert result == PlayerLoadResult(
        player_ids_found=2,
        players_resolved=2,
        players_loaded=2,
    )


def test_resolved_count_can_differ_from_ids_found():
    connection = MagicMock()
    player_ids = [1001, 1002, 1003]
    players = [
        MlbPlayer(mlb_player_id=1001, full_name="Ada Batter"),
        MlbPlayer(mlb_player_id=1002, full_name="Pat Pitcher"),
    ]

    with (
        patch(
            "app.curated.player_loader.get_statcast_player_ids",
            return_value=player_ids,
        ),
        patch(
            "app.curated.player_loader.fetch_mlb_players",
            return_value=players,
        ) as mock_fetch,
        patch(
            "app.curated.player_loader.load_mlb_players",
            return_value=2,
        ) as mock_load,
    ):
        result = load_players_from_statcast(connection)

    mock_fetch.assert_called_once_with(player_ids)
    mock_load.assert_called_once_with(connection, players)
    assert result == PlayerLoadResult(
        player_ids_found=3,
        players_resolved=2,
        players_loaded=2,
    )


def test_api_errors_propagate_and_loader_is_not_called():
    connection = MagicMock()

    with (
        patch(
            "app.curated.player_loader.get_statcast_player_ids",
            return_value=[1001],
        ),
        patch(
            "app.curated.player_loader.fetch_mlb_players",
            side_effect=RuntimeError("mlb api failed"),
        ),
        patch("app.curated.player_loader.load_mlb_players") as mock_load,
    ):
        with pytest.raises(RuntimeError, match="mlb api failed"):
            load_players_from_statcast(connection)

    mock_load.assert_not_called()


def test_database_loader_errors_propagate():
    connection = MagicMock()
    players = [MlbPlayer(mlb_player_id=1001, full_name="Ada Batter")]

    with (
        patch(
            "app.curated.player_loader.get_statcast_player_ids",
            return_value=[1001],
        ),
        patch(
            "app.curated.player_loader.fetch_mlb_players",
            return_value=players,
        ),
        patch(
            "app.curated.player_loader.load_mlb_players",
            side_effect=RuntimeError("player upsert failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="player upsert failed"):
            load_players_from_statcast(connection)
