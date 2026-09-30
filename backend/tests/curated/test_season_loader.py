"""Tests for curated MLB season-loading orchestration."""

from contextlib import contextmanager
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.season_data import SeasonLoadResult
from app.curated.season_loader import load_mlb_seasons


_MLB_SEASON_YEARS = [2022, 2023, 2024, 2025, 2026]

_EXPECTED_SEASONS = {
    2022: {
        "all_star_date": date(2022, 7, 19),
        "trade_deadline_date": date(2022, 8, 2),
    },
    2023: {
        "all_star_date": date(2023, 7, 11),
        "trade_deadline_date": date(2023, 8, 1),
    },
    2024: {
        "all_star_date": date(2024, 7, 16),
        "trade_deadline_date": date(2024, 7, 30),
    },
    2025: {
        "all_star_date": date(2025, 7, 15),
        "trade_deadline_date": date(2025, 7, 31),
    },
    2026: {
        "all_star_date": date(2026, 7, 14),
        "trade_deadline_date": date(2026, 8, 3),
    },
}


def _create_engine() -> Engine:
    return create_engine(settings.database_url)


@contextmanager
def _isolated_connection(engine: Engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def _fetch_season(connection: Connection, season_year: int):
    return connection.execute(
        text(
            """
            SELECT
                season_id,
                season_year,
                all_star_date,
                trade_deadline_date
            FROM curated.season
            WHERE season_year = :season_year
            """
        ),
        {"season_year": season_year},
    ).mappings().one()


def _count_seasons(connection: Connection, season_years: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.season
            WHERE season_year = ANY(:season_years)
            """
        ),
        {"season_years": season_years},
    ).scalar_one()


def test_load_mlb_seasons_loads_documented_seasons():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_seasons(connection)

            assert result == SeasonLoadResult(seasons_loaded=5)
            assert _count_seasons(connection, _MLB_SEASON_YEARS) == 5
            for season_year, expected in _EXPECTED_SEASONS.items():
                season = _fetch_season(connection, season_year)
                assert season["season_year"] == season_year
                assert season["all_star_date"] == expected["all_star_date"]
                assert (
                    season["trade_deadline_date"]
                    == expected["trade_deadline_date"]
                )
                assert season["season_id"] is not None
    finally:
        engine.dispose()


def test_load_mlb_seasons_is_idempotent():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            first_result = load_mlb_seasons(connection)
            original_ids = {
                season_year: _fetch_season(connection, season_year)["season_id"]
                for season_year in _MLB_SEASON_YEARS
            }

            second_result = load_mlb_seasons(connection)

            assert first_result == SeasonLoadResult(seasons_loaded=5)
            assert second_result == SeasonLoadResult(seasons_loaded=5)
            assert _count_seasons(connection, _MLB_SEASON_YEARS) == 5
            for season_year, expected in _EXPECTED_SEASONS.items():
                season = _fetch_season(connection, season_year)
                assert season["season_id"] == original_ids[season_year]
                assert season["all_star_date"] == expected["all_star_date"]
                assert (
                    season["trade_deadline_date"]
                    == expected["trade_deadline_date"]
                )
    finally:
        engine.dispose()
