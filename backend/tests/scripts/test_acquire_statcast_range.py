"""Tests for 5-day Statcast acquisition CLI."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.acquire_statcast_range import _date_chunks, main


def _write_csv(path: Path, data_rows: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        handle.write("game_pk\n")
        for index in range(data_rows):
            handle.write(f"{index}\n")
    return path


def _tmp_output_path(tmp_path: Path):
    def output_path(start_date: date, end_date: date) -> Path:
        return tmp_path / (
            f"statcast_{start_date.isoformat()}_{end_date.isoformat()}.csv"
        )

    return output_path


def test_five_day_chunks_cross_month_boundary():
    chunks = _date_chunks(date(2022, 4, 28), date(2022, 5, 4))

    assert chunks == [
        (date(2022, 4, 28), date(2022, 5, 2)),
        (date(2022, 5, 3), date(2022, 5, 4)),
    ]


def test_final_chunk_is_shorter_than_five_days():
    chunks = _date_chunks(date(2022, 4, 7), date(2022, 4, 30))

    assert chunks == [
        (date(2022, 4, 7), date(2022, 4, 11)),
        (date(2022, 4, 12), date(2022, 4, 16)),
        (date(2022, 4, 17), date(2022, 4, 21)),
        (date(2022, 4, 22), date(2022, 4, 26)),
        (date(2022, 4, 27), date(2022, 4, 30)),
    ]
    assert (chunks[-1][1] - chunks[-1][0]).days + 1 == 4


def test_single_day_range():
    chunks = _date_chunks(date(2022, 4, 7), date(2022, 4, 7))

    assert chunks == [(date(2022, 4, 7), date(2022, 4, 7))]


def test_multi_week_range():
    chunks = _date_chunks(date(2022, 4, 7), date(2022, 4, 27))

    assert chunks == [
        (date(2022, 4, 7), date(2022, 4, 11)),
        (date(2022, 4, 12), date(2022, 4, 16)),
        (date(2022, 4, 17), date(2022, 4, 21)),
        (date(2022, 4, 22), date(2022, 4, 26)),
        (date(2022, 4, 27), date(2022, 4, 27)),
    ]


def test_start_date_after_end_date_exits_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        main(["2022-04-09", "2022-04-07"])

    assert exc_info.value.code != 0


def test_invalid_iso_dates_exit_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        main(["04-07-2022", "2022-04-09"])

    assert exc_info.value.code != 0


def test_main_downloads_each_five_day_chunk(tmp_path, capsys):
    calls: list[tuple[date, date, Path]] = []

    def fake_download(start_date: date, end_date: date, output_path: Path) -> Path:
        calls.append((start_date, end_date, output_path))
        return _write_csv(output_path, data_rows=2)

    with patch(
        "scripts.acquire_statcast_range.download_statcast_csv",
        side_effect=fake_download,
    ), patch(
        "scripts.acquire_statcast_range._output_path",
        side_effect=_tmp_output_path(tmp_path),
    ):
        result = main(["2022-04-07", "2022-04-16"])

    assert result == 0
    assert [chunk[:2] for chunk in calls] == [
        (date(2022, 4, 7), date(2022, 4, 11)),
        (date(2022, 4, 12), date(2022, 4, 16)),
    ]
    output = capsys.readouterr().out
    assert "Range: 2022-04-07 to 2022-04-16" in output
    assert "Chunks: 2" in output
    assert "[1/2] 2022-04-07 to 2022-04-11" in output
    assert "[2/2] 2022-04-12 to 2022-04-16" in output


def test_25000_row_artifact_is_rejected(tmp_path, capsys):
    def fake_download(start_date: date, end_date: date, output_path: Path) -> Path:
        return _write_csv(output_path, data_rows=25_000)

    with patch(
        "scripts.acquire_statcast_range.download_statcast_csv",
        side_effect=fake_download,
    ), patch(
        "scripts.acquire_statcast_range._output_path",
        side_effect=_tmp_output_path(tmp_path),
    ):
        result = main(["2022-04-07", "2022-04-11"])

    captured = capsys.readouterr()
    assert result == 1
    assert "2022-04-07 to 2022-04-11" in captured.err
    assert "25,000-row limit" in captured.err
    assert "exactly 25000 data rows" in captured.err
    assert "Saved:" not in captured.out
