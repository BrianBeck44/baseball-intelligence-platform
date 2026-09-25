"""Unit tests for the MLB Stats API people client."""

import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from app.mlb.stats_api import MlbPlayer, MlbStatsApiError, fetch_mlb_players


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
