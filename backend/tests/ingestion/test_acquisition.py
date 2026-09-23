"""Unit tests for Statcast CSV acquisition."""

from datetime import date
from email.message import EmailMessage
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from app.ingestion.acquisition import download_statcast_csv


CSV_BYTES = b"game_pk,game_type\n661032,R\n"


def _urlopen_context(payload: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = payload
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    return context


def test_successful_download_writes_response_bytes(tmp_path):
    output_path = tmp_path / "statcast.csv"

    with patch(
        "app.ingestion.acquisition.urlopen",
        return_value=_urlopen_context(CSV_BYTES),
    ) as mock_urlopen:
        result = download_statcast_csv(
            start_date=date(2022, 4, 7),
            end_date=date(2022, 4, 9),
            output_path=output_path,
        )

    mock_urlopen.assert_called_once()
    assert result == output_path
    assert output_path.is_file()
    assert output_path.read_bytes() == CSV_BYTES


def test_creates_missing_parent_directories(tmp_path):
    output_path = tmp_path / "raw" / "statcast" / "sample.csv"
    assert not output_path.parent.exists()

    with patch(
        "app.ingestion.acquisition.urlopen",
        return_value=_urlopen_context(CSV_BYTES),
    ):
        result = download_statcast_csv(
            start_date=date(2022, 4, 7),
            end_date=date(2022, 4, 9),
            output_path=output_path,
        )

    assert result == output_path
    assert output_path.parent.is_dir()
    assert output_path.read_bytes() == CSV_BYTES


def test_httperror_raises_oserror_with_status_code(tmp_path):
    output_path = tmp_path / "statcast.csv"
    http_error = HTTPError(
        url="https://baseballsavant.mlb.com/statcast_search/csv",
        code=503,
        msg="Service Unavailable",
        hdrs=EmailMessage(),
        fp=None,
    )

    with patch(
        "app.ingestion.acquisition.urlopen",
        side_effect=http_error,
    ):
        with pytest.raises(OSError, match="503") as exc_info:
            download_statcast_csv(
                start_date=date(2022, 4, 7),
                end_date=date(2022, 4, 9),
                output_path=output_path,
            )

    assert not output_path.exists()
    assert isinstance(exc_info.value, OSError)


def test_urlerror_raises_oserror(tmp_path):
    output_path = tmp_path / "statcast.csv"

    with patch(
        "app.ingestion.acquisition.urlopen",
        side_effect=URLError("timed out"),
    ):
        with pytest.raises(OSError):
            download_statcast_csv(
                start_date=date(2022, 4, 7),
                end_date=date(2022, 4, 9),
                output_path=output_path,
            )

    assert not output_path.exists()


def test_empty_response_raises_oserror(tmp_path):
    output_path = tmp_path / "statcast.csv"

    with patch(
        "app.ingestion.acquisition.urlopen",
        return_value=_urlopen_context(b""),
    ):
        with pytest.raises(OSError):
            download_statcast_csv(
                start_date=date(2022, 4, 7),
                end_date=date(2022, 4, 9),
                output_path=output_path,
            )

    assert not output_path.exists()


def test_request_contains_expected_query_parameters(tmp_path):
    output_path = tmp_path / "statcast.csv"
    captured: dict[str, Request] = {}

    def capture_urlopen(request: Request):
        captured["request"] = request
        return _urlopen_context(CSV_BYTES)

    with patch(
        "app.ingestion.acquisition.urlopen",
        side_effect=capture_urlopen,
    ):
        download_statcast_csv(
            start_date=date(2022, 4, 7),
            end_date=date(2022, 4, 9),
            output_path=output_path,
        )

    request = captured["request"]
    assert isinstance(request, Request)
    url = request.full_url
    assert "all=true" in url
    assert "type=details" in url
    assert "game_date_gt=2022-04-07" in url
    assert "game_date_lt=2022-04-09" in url
