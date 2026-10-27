"""Download Statcast CSV artifacts from Baseball Savant."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STATCAST_SEARCH_CSV_URL = "https://baseballsavant.mlb.com/statcast_search/csv"


def download_statcast_csv(
    start_date: date,
    end_date: date,
    output_path: Path,
) -> Path:
    """Download Statcast pitch-level CSV for an inclusive date range.

    Writes the Baseball Savant response to ``output_path`` without
    transforming the payload. Parent directories are created if needed.
    """
    query = urlencode(
        {
            "all": "true",
            "type": "details",
            "game_date_gt": start_date.isoformat(),
            "game_date_lt": end_date.isoformat(),
        }
    )
    request = Request(
        f"{STATCAST_SEARCH_CSV_URL}?{query}",
        headers={"User-Agent": "baseball-intelligence-platform/statcast-acquisition"},
    )

    try:
        with urlopen(request, timeout=60) as response:
            status_code = getattr(response, "status", None)
            payload = response.read()
    except HTTPError as exc:
        raise OSError(
            f"Baseball Savant request failed with HTTP {exc.code} "
            f"for {start_date.isoformat()} to {end_date.isoformat()}."
        ) from exc
    except URLError as exc:
        raise OSError(
            "Unable to retrieve Statcast CSV from Baseball Savant: "
            f"{exc.reason}"
        ) from exc

    if status_code not in (None, 200):
        raise OSError(
            f"Baseball Savant returned HTTP {status_code} "
            f"for {start_date.isoformat()} to {end_date.isoformat()}."
        )
    if not payload:
        raise OSError(
            "Baseball Savant returned an empty response for "
            f"{start_date.isoformat()} to {end_date.isoformat()}."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    return output_path
