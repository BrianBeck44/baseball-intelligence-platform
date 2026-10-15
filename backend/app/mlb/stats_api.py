"""MLB Stats API client.

Network access for MLB people and team lookups is isolated here. This
module does not query or write to PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from json import JSONDecodeError, loads
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
_PLAYER_ID_BATCH_SIZE = 100


@dataclass(frozen=True)
class MlbPlayer:
    mlb_player_id: int
    full_name: str


@dataclass(frozen=True)
class MlbTeam:
    code: str
    name: str


class MlbStatsApiError(ValueError):
    """Raised when the MLB Stats API response cannot be used."""


def fetch_mlb_players(player_ids: Collection[int]) -> list[MlbPlayer]:
    """Return player ID and full name for the given MLB person IDs.

    Issues ``/api/v1/people`` requests using the ``personIds`` query
    parameter in batches of 100 unique IDs. An empty collection
    returns no players and does not call the API.
    """
    unique_ids = _unique_player_ids(player_ids)
    if not unique_ids:
        return []

    players: list[MlbPlayer] = []
    for batch in _player_id_batches(unique_ids):
        payload = _get_json(_people_url(batch))
        players.extend(_parse_people(payload))
    return players


def fetch_mlb_teams(
    team_codes: Collection[str],
    seasons: Collection[int],
) -> list[MlbTeam]:
    """Return MLB team code and name for the requested abbreviations.

    Issues one ``/api/v1/teams?sportId=1&season={year}`` request for each
    distinct Statcast year, then one current ``/api/v1/teams?sportId=1``
    request. Only records whose abbreviation is in ``team_codes`` are
    kept. An empty code collection returns no teams and does not call
    the API.

    When the same code appears in more than one requested season, the
    name from the latest year is used. Current-list records fill in
    codes that no season response contained.
    """
    unique_codes = _unique_team_codes(team_codes)
    if not unique_codes:
        return []

    requested_codes = set(unique_codes)
    teams_by_code: dict[str, MlbTeam] = {}
    for year in _unique_seasons(seasons):
        payload = _get_json(_mlb_teams_url(season=year))
        teams_by_code.update(
            _teams_by_requested_code(_parse_teams(payload), requested_codes)
        )

    payload = _get_json(_mlb_teams_url())
    for code, team in _teams_by_requested_code(
        _parse_teams(payload),
        requested_codes,
    ).items():
        if code not in teams_by_code:
            teams_by_code[code] = team

    return [teams_by_code[code] for code in unique_codes if code in teams_by_code]


def _player_id_batches(player_ids: list[int]) -> list[list[int]]:
    size = _PLAYER_ID_BATCH_SIZE
    return [player_ids[index:index + size] for index in range(0, len(player_ids), size)]


def _unique_player_ids(player_ids: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for player_id in player_ids:
        if player_id in seen:
            continue
        seen.add(player_id)
        ordered.append(player_id)
    return ordered


def _unique_team_codes(team_codes: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for team_code in team_codes:
        if team_code in seen:
            continue
        seen.add(team_code)
        ordered.append(team_code)
    return ordered


def _unique_seasons(seasons: Iterable[int]) -> list[int]:
    return sorted({int(season) for season in seasons})


def _mlb_teams_url(season: int | None = None) -> str:
    query: dict[str, str] = {"sportId": "1"}
    if season is not None:
        query["season"] = str(season)
    return f"{TEAMS_URL}?{urlencode(query)}"


def _teams_by_requested_code(
    teams: Iterable[MlbTeam],
    requested_codes: set[str],
) -> dict[str, MlbTeam]:
    teams_by_code: dict[str, MlbTeam] = {}
    for team in teams:
        if team.code not in requested_codes:
            continue
        existing = teams_by_code.get(team.code)
        if existing is not None and existing != team:
            raise MlbStatsApiError(
                "MLB Stats API returned conflicting teams for abbreviation "
                f"'{team.code}'."
            )
        teams_by_code[team.code] = team
    return teams_by_code


def _people_url(player_ids: Collection[int]) -> str:
    query = urlencode(
        {"personIds": ",".join(str(player_id) for player_id in player_ids)}
    )
    return f"{PEOPLE_URL}?{query}"


def _get_json(url: str) -> object:
    request = Request(
        url,
        headers={"User-Agent": "baseball-intelligence-platform/mlb-stats-api"},
        method="GET",
    )
    try:
        with urlopen(request) as response:
            status_code = getattr(response, "status", None)
            body = response.read()
    except HTTPError as exc:
        raise OSError(
            f"MLB Stats API request failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise OSError(
            f"Unable to retrieve MLB Stats API people: {exc.reason}"
        ) from exc

    if status_code not in (None, 200):
        raise OSError(f"MLB Stats API returned HTTP {status_code}.")

    try:
        return loads(body.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise MlbStatsApiError(
            "MLB Stats API returned a response that is not valid JSON."
        ) from exc


def _parse_people(payload: object) -> list[MlbPlayer]:
    if not isinstance(payload, dict):
        raise MlbStatsApiError(
            "MLB Stats API people response must be a JSON object."
        )

    if "people" not in payload:
        raise MlbStatsApiError(
            "MLB Stats API people response is missing the 'people' field."
        )

    people = payload["people"]
    if not isinstance(people, list):
        raise MlbStatsApiError("MLB Stats API 'people' field must be a list.")

    return [_parse_person(record, index) for index, record in enumerate(people)]


def _parse_person(record: object, index: int) -> MlbPlayer:
    if not isinstance(record, dict):
        raise MlbStatsApiError(
            f"MLB Stats API person at index {index} must be an object."
        )

    player_id = record.get("id")
    full_name = record.get("fullName")

    if isinstance(player_id, bool) or not isinstance(player_id, int):
        raise MlbStatsApiError(
            f"MLB Stats API person at index {index} is missing a valid 'id'."
        )
    if not isinstance(full_name, str) or not full_name:
        raise MlbStatsApiError(
            f"MLB Stats API person at index {index} is missing a valid 'fullName'."
        )

    return MlbPlayer(mlb_player_id=player_id, full_name=full_name)


def _parse_teams(payload: object) -> list[MlbTeam]:
    if not isinstance(payload, dict):
        raise MlbStatsApiError(
            "MLB Stats API teams response must be a JSON object."
        )

    if "teams" not in payload:
        raise MlbStatsApiError(
            "MLB Stats API teams response is missing the 'teams' field."
        )

    teams = payload["teams"]
    if not isinstance(teams, list):
        raise MlbStatsApiError("MLB Stats API 'teams' field must be a list.")

    return [_parse_team(record, index) for index, record in enumerate(teams)]


def _parse_team(record: object, index: int) -> MlbTeam:
    if not isinstance(record, dict):
        raise MlbStatsApiError(
            f"MLB Stats API team at index {index} must be an object."
        )

    abbreviation = record.get("abbreviation")
    name = record.get("name")

    if not isinstance(abbreviation, str) or not abbreviation:
        raise MlbStatsApiError(
            f"MLB Stats API team at index {index} is missing a valid "
            f"'abbreviation'."
        )
    if not isinstance(name, str) or not name:
        raise MlbStatsApiError(
            f"MLB Stats API team at index {index} is missing a valid 'name'."
        )

    return MlbTeam(code=abbreviation, name=name)
