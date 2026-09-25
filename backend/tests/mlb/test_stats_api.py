"""Unit tests for the MLB Stats API client."""

import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from app.mlb.stats_api import (
    MlbPlayer,
    MlbStatsApiError,
    MlbTeam,
    fetch_mlb_players,
    fetch_mlb_teams,
)


def _urlopen_context(payload: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = payload
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


def _people_payload(people: list[dict]) -> bytes:
    return json.dumps({"people": people}).encode("utf-8")


def _teams_payload(payload: object) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_empty_player_ids_does_not_make_http_request():
    with patch("app.mlb.stats_api.urlopen") as mock_urlopen:
        result = fetch_mlb_players([])

    assert result == []
    mock_urlopen.assert_not_called()


def test_successful_bulk_response_returns_typed_player():
    payload = _people_payload(
        [{"id": 545361, "fullName": "Mike Trout"}]
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ) as mock_urlopen:
        result = fetch_mlb_players([545361, 545361])

    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    assert isinstance(request, Request)
    query = parse_qs(urlparse(request.full_url).query)
    assert query["personIds"] == ["545361"]
    assert result == [MlbPlayer(mlb_player_id=545361, full_name="Mike Trout")]


def test_multiple_returned_players_use_one_request():
    payload = _people_payload(
        [
            {"id": 545361, "fullName": "Mike Trout"},
            {"id": 660271, "fullName": "Shohei Ohtani"},
        ]
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ) as mock_urlopen:
        result = fetch_mlb_players([545361, 660271])

    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    query = parse_qs(urlparse(request.full_url).query)
    assert query["personIds"] == ["545361,660271"]
    assert result == [
        MlbPlayer(mlb_player_id=545361, full_name="Mike Trout"),
        MlbPlayer(mlb_player_id=660271, full_name="Shohei Ohtani"),
    ]


@pytest.mark.parametrize(
    "people",
    [
        [{"fullName": "Mike Trout"}],
        [{"id": 545361}],
        [{"id": 545361, "fullName": ""}],
        ["not-an-object"],
    ],
)
def test_malformed_or_missing_player_data_raises(people):
    payload = _people_payload(people)

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_players([545361])


def test_valid_teams_response_is_parsed():
    payload = _teams_payload(
        {"teams": [{"abbreviation": "LAA", "name": "Los Angeles Angels"}]}
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ) as mock_urlopen:
        result = fetch_mlb_teams()

    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    assert isinstance(request, Request)
    assert request.full_url == "https://statsapi.mlb.com/api/v1/teams"
    assert result == [MlbTeam(code="LAA", name="Los Angeles Angels")]


def test_multiple_teams_are_returned():
    payload = _teams_payload(
        {
            "teams": [
                {"abbreviation": "LAA", "name": "Los Angeles Angels"},
                {"abbreviation": "HOU", "name": "Houston Astros"},
            ]
        }
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ) as mock_urlopen:
        result = fetch_mlb_teams()

    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://statsapi.mlb.com/api/v1/teams"
    assert result == [
        MlbTeam(code="LAA", name="Los Angeles Angels"),
        MlbTeam(code="HOU", name="Houston Astros"),
    ]


def test_missing_teams_field_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_teams_field_not_a_list_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({"teams": {"LAA": "Angels"}})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_team_record_not_an_object_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({"teams": ["LAA"]})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_team_missing_abbreviation_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"name": "Los Angeles Angels"}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_team_empty_abbreviation_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload(
                {"teams": [{"abbreviation": "", "name": "Los Angeles Angels"}]}
            )
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_team_missing_name_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"abbreviation": "LAA"}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()


def test_team_empty_name_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"abbreviation": "LAA", "name": ""}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams()
