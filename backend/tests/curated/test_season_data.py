"""Tests for curated.season upserts."""

from contextlib import contextmanager
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.season_data import CuratedSeason, SeasonLoadResult, load_seasons


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


def _fetch_all_seasons(connection: Connection):
    return connection.execute(
        text(
            """
            SELECT
                season_id,
                season_year,
                all_star_date,
                trade_deadline_date
            FROM curated.season
            ORDER BY season_id
            """
        )
    ).mappings().all()


def test_empty_input_returns_zero_and_does_not_insert():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            before = _fetch_all_seasons(connection)

            result = load_seasons(connection, [])

            assert result == SeasonLoadResult(seasons_loaded=0)
            assert _fetch_all_seasons(connection) == before
    finally:
        engine.dispose()


def test_single_season_is_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            result = load_seasons(
                connection,
                [
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 19),
                        trade_deadline_date=date(2022, 8, 2),
                    )
                ],
            )

            assert result == SeasonLoadResult(seasons_loaded=1)
            season = _fetch_season(connection, 2022)
            assert season["season_year"] == 2022
            assert season["all_star_date"] == date(2022, 7, 19)
            assert season["trade_deadline_date"] == date(2022, 8, 2)
            assert season["season_id"] is not None
    finally:
        engine.dispose()


def test_multiple_seasons_are_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            result = load_seasons(
                connection,
                [
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 19),
                        trade_deadline_date=date(2022, 8, 2),
                    ),
                    CuratedSeason(
                        season_year=2023,
                        all_star_date=date(2023, 7, 11),
                        trade_deadline_date=date(2023, 8, 1),
                    ),
                ],
            )

            assert result == SeasonLoadResult(seasons_loaded=2)
            assert _count_seasons(connection, [2022, 2023]) == 2
            first = _fetch_season(connection, 2022)
            second = _fetch_season(connection, 2023)
            assert first["all_star_date"] == date(2022, 7, 19)
            assert first["trade_deadline_date"] == date(2022, 8, 2)
            assert second["all_star_date"] == date(2023, 7, 11)
            assert second["trade_deadline_date"] == date(2023, 8, 1)
    finally:
        engine.dispose()


def test_duplicate_season_years_use_last_supplied_record():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            result = load_seasons(
                connection,
                [
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 1),
                        trade_deadline_date=date(2022, 7, 31),
                    ),
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 19),
                        trade_deadline_date=date(2022, 8, 2),
                    ),
                ],
            )

            assert result == SeasonLoadResult(seasons_loaded=1)
            assert _count_seasons(connection, [2022]) == 1
            season = _fetch_season(connection, 2022)
            assert season["all_star_date"] == date(2022, 7, 19)
            assert season["trade_deadline_date"] == date(2022, 8, 2)
    finally:
        engine.dispose()


def test_existing_season_is_updated_and_season_id_is_preserved():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            load_seasons(
                connection,
                [
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 19),
                        trade_deadline_date=date(2022, 8, 2),
                    )
                ],
            )
            original = _fetch_season(connection, 2022)

            result = load_seasons(
                connection,
                [
                    CuratedSeason(
                        season_year=2022,
                        all_star_date=date(2022, 7, 20),
                        trade_deadline_date=date(2022, 8, 3),
                    )
                ],
            )

            assert result == SeasonLoadResult(seasons_loaded=1)
            updated = _fetch_season(connection, 2022)
            assert updated["season_id"] == original["season_id"]
            assert updated["season_year"] == 2022
            assert updated["all_star_date"] == date(2022, 7, 20)
            assert updated["trade_deadline_date"] == date(2022, 8, 3)
            assert _count_seasons(connection, [2022]) == 1
    finally:
        engine.dispose()
