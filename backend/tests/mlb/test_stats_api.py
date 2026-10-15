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


def _requested_person_ids(url: str) -> list[str]:
    query = parse_qs(urlparse(url).query)
    return query["personIds"][0].split(",")


def test_fewer_than_100_ids_makes_one_request():
    player_ids = list(range(1, 50))

    with patch(
        "app.mlb.stats_api._get_json",
        return_value={"people": []},
    ) as mock_get_json:
        result = fetch_mlb_players(player_ids)

    mock_get_json.assert_called_once()
    assert _requested_person_ids(mock_get_json.call_args.args[0]) == [
        str(player_id) for player_id in player_ids
    ]
    assert result == []


def test_exactly_100_ids_makes_one_request():
    player_ids = list(range(1, 101))

    with patch(
        "app.mlb.stats_api._get_json",
        return_value={"people": []},
    ) as mock_get_json:
        fetch_mlb_players(player_ids)

    mock_get_json.assert_called_once()
    requested = _requested_person_ids(mock_get_json.call_args.args[0])
    assert len(requested) == 100
    assert requested == [str(player_id) for player_id in player_ids]


def test_more_than_100_ids_makes_multiple_requests():
    player_ids = list(range(1, 102))
    first_payload = {
        "people": [
            {"id": player_id, "fullName": f"Player {player_id}"}
            for player_id in range(1, 101)
        ]
    }
    second_payload = {"people": [{"id": 101, "fullName": "Player 101"}]}

    with patch(
        "app.mlb.stats_api._get_json",
        side_effect=[first_payload, second_payload],
    ) as mock_get_json:
        result = fetch_mlb_players(player_ids)

    assert mock_get_json.call_count == 2
    assert _requested_person_ids(mock_get_json.call_args_list[0].args[0]) == [
        str(player_id) for player_id in range(1, 101)
    ]
    assert _requested_person_ids(mock_get_json.call_args_list[1].args[0]) == ["101"]
    assert result == [
        MlbPlayer(mlb_player_id=player_id, full_name=f"Player {player_id}")
        for player_id in player_ids
    ]


def test_duplicate_ids_are_not_requested_twice():
    player_ids = list(range(1, 151)) + list(range(1, 151))

    with patch(
        "app.mlb.stats_api._get_json",
        side_effect=[{"people": []}, {"people": []}],
    ) as mock_get_json:
        fetch_mlb_players(player_ids)

    assert mock_get_json.call_count == 2
    requested = [
        person_id
        for call in mock_get_json.call_args_list
        for person_id in _requested_person_ids(call.args[0])
    ]
    assert requested == [str(player_id) for player_id in range(1, 151)]
    assert len(requested) == len(set(requested))


def test_empty_player_ids_does_not_call_get_json():
    with patch("app.mlb.stats_api._get_json") as mock_get_json:
        result = fetch_mlb_players([])

    assert result == []
    mock_get_json.assert_not_called()


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


def _mlb_teams_query(request: Request) -> dict[str, list[str]]:
    parsed = urlparse(request.full_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "statsapi.mlb.com"
    assert parsed.path == "/api/v1/teams"
    return parse_qs(parsed.query)


def test_empty_team_codes_does_not_make_http_request():
    with patch("app.mlb.stats_api.urlopen") as mock_urlopen:
        result = fetch_mlb_teams([], [2022])

    assert result == []
    mock_urlopen.assert_not_called()


def test_current_mlb_request_includes_sport_id_and_omits_season():
    payload = _teams_payload(
        {"teams": [{"abbreviation": "LAA", "name": "Los Angeles Angels"}]}
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ) as mock_urlopen:
        result = fetch_mlb_teams(["LAA"], [])

    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    assert isinstance(request, Request)
    query = _mlb_teams_query(request)
    assert query == {"sportId": ["1"]}
    assert result == [MlbTeam(code="LAA", name="Los Angeles Angels")]


def test_historical_and_current_mlb_requests_are_made():
    season_payload = _teams_payload(
        {"teams": [{"abbreviation": "ATL", "name": "Atlanta Braves"}]}
    )
    current_payload = _teams_payload(
        {"teams": [{"abbreviation": "ATH", "name": "Athletics"}]}
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        side_effect=[
            _urlopen_context(season_payload),
            _urlopen_context(current_payload),
        ],
    ) as mock_urlopen:
        result = fetch_mlb_teams(["ATL", "ATH"], [2022])

    assert mock_urlopen.call_count == 2
    season_query = _mlb_teams_query(mock_urlopen.call_args_list[0].args[0])
    current_query = _mlb_teams_query(mock_urlopen.call_args_list[1].args[0])
    assert season_query == {"sportId": ["1"], "season": ["2022"]}
    assert current_query == {"sportId": ["1"]}
    assert result == [
        MlbTeam(code="ATL", name="Atlanta Braves"),
        MlbTeam(code="ATH", name="Athletics"),
    ]


def test_unfiltered_teams_url_is_not_requested():
    payload = _teams_payload(
        {"teams": [{"abbreviation": "NYY", "name": "New York Yankees"}]}
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        side_effect=[
            _urlopen_context(payload),
            _urlopen_context(payload),
        ],
    ) as mock_urlopen:
        fetch_mlb_teams(["NYY"], [2022])

    requested_urls = [
        call.args[0].full_url for call in mock_urlopen.call_args_list
    ]
    assert "https://statsapi.mlb.com/api/v1/teams" not in requested_urls
    for request in (call.args[0] for call in mock_urlopen.call_args_list):
        assert _mlb_teams_query(request)["sportId"] == ["1"]


def test_multiple_seasons_are_requested_in_sorted_order():
    payload_2022 = _teams_payload(
        {"teams": [{"abbreviation": "OAK", "name": "Oakland Athletics"}]}
    )
    payload_2025 = _teams_payload(
        {"teams": [{"abbreviation": "ATH", "name": "Athletics"}]}
    )
    current_payload = _teams_payload({"teams": []})

    with patch(
        "app.mlb.stats_api.urlopen",
        side_effect=[
            _urlopen_context(payload_2022),
            _urlopen_context(payload_2025),
            _urlopen_context(current_payload),
        ],
    ) as mock_urlopen:
        result = fetch_mlb_teams(["OAK", "ATH"], [2025, 2022, 2022])

    assert mock_urlopen.call_count == 3
    assert _mlb_teams_query(mock_urlopen.call_args_list[0].args[0]) == {
        "sportId": ["1"],
        "season": ["2022"],
    }
    assert _mlb_teams_query(mock_urlopen.call_args_list[1].args[0]) == {
        "sportId": ["1"],
        "season": ["2025"],
    }
    assert _mlb_teams_query(mock_urlopen.call_args_list[2].args[0]) == {
        "sportId": ["1"]
    }
    assert result == [
        MlbTeam(code="OAK", name="Oakland Athletics"),
        MlbTeam(code="ATH", name="Athletics"),
    ]


def test_latest_season_name_is_used_for_the_same_code():
    payload_2022 = _teams_payload(
        {"teams": [{"abbreviation": "CLE", "name": "Cleveland Guardians"}]}
    )
    payload_2025 = _teams_payload(
        {"teams": [{"abbreviation": "CLE", "name": "Cleveland Guardians 2025"}]}
    )
    current_payload = _teams_payload(
        {"teams": [{"abbreviation": "CLE", "name": "Current Cleveland"}]}
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        side_effect=[
            _urlopen_context(payload_2022),
            _urlopen_context(payload_2025),
            _urlopen_context(current_payload),
        ],
    ):
        result = fetch_mlb_teams(["CLE"], [2022, 2025])

    assert result == [MlbTeam(code="CLE", name="Cleveland Guardians 2025")]


def test_unrequested_teams_are_not_returned():
    payload = _teams_payload(
        {
            "teams": [
                {"abbreviation": "LAA", "name": "Los Angeles Angels"},
                {"abbreviation": "HOU", "name": "Houston Astros"},
                {"abbreviation": "AAA", "name": "Scranton/Wilkes-Barre RailRiders"},
            ]
        }
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ):
        result = fetch_mlb_teams(["HOU", "LAA"], [])

    assert result == [
        MlbTeam(code="HOU", name="Houston Astros"),
        MlbTeam(code="LAA", name="Los Angeles Angels"),
    ]


def test_conflicting_abbreviations_in_one_response_raise():
    payload = _teams_payload(
        {
            "teams": [
                {"abbreviation": "ATL", "name": "Atlanta Braves"},
                {"abbreviation": "ATL", "name": "Braves Alternate Training Site"},
            ]
        }
    )

    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(payload),
    ):
        with pytest.raises(MlbStatsApiError, match="conflicting teams"):
            fetch_mlb_teams(["ATL"], [])


def test_http_errors_propagate():
    with patch(
        "app.mlb.stats_api.urlopen",
        side_effect=OSError("mlb api failed"),
    ):
        with pytest.raises(OSError, match="mlb api failed"):
            fetch_mlb_teams(["LAA"], [])


def test_missing_teams_field_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])


def test_teams_field_not_a_list_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({"teams": {"LAA": "Angels"}})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])


def test_team_record_not_an_object_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(_teams_payload({"teams": ["LAA"]})),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])


def test_team_missing_abbreviation_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"name": "Los Angeles Angels"}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])


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
            fetch_mlb_teams(["LAA"], [])


def test_team_missing_name_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"abbreviation": "LAA"}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])


def test_team_empty_name_raises():
    with patch(
        "app.mlb.stats_api.urlopen",
        return_value=_urlopen_context(
            _teams_payload({"teams": [{"abbreviation": "LAA", "name": ""}]})
        ),
    ):
        with pytest.raises(MlbStatsApiError):
            fetch_mlb_teams(["LAA"], [])
