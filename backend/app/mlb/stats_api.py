"""MLB Stats API client.

Network access for MLB people lookups is isolated here. This module
does not query or write to PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from json import JSONDecodeError, loads
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"


@dataclass(frozen=True)
class MlbPlayer:
    mlb_player_id: int
    full_name: str


class MlbStatsApiError(ValueError):
    """Raised when the MLB Stats API response cannot be used."""


def fetch_mlb_players(player_ids: Collection[int]) -> list[MlbPlayer]:
    """Return player ID and full name for the given MLB person IDs.

    Issues one ``/api/v1/people`` request using the ``personIds``
    query parameter. An empty collection returns no players and does
    not call the API.
    """
    unique_ids = _unique_player_ids(player_ids)
    if not unique_ids:
        return []

    payload = _get_json(_people_url(unique_ids))
    return _parse_people(payload)


def _unique_player_ids(player_ids: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for player_id in player_ids:
        if player_id in seen:
            continue
        seen.add(player_id)
        ordered.append(player_id)
    return ordered


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
