"""Load known MLB season definitions into curated.season."""

from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection

from app.curated.season_data import CuratedSeason, SeasonLoadResult, load_seasons


MLB_SEASONS = (
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
    CuratedSeason(
        season_year=2024,
        all_star_date=date(2024, 7, 16),
        trade_deadline_date=date(2024, 7, 30),
    ),
    CuratedSeason(
        season_year=2025,
        all_star_date=date(2025, 7, 15),
        trade_deadline_date=date(2025, 7, 31),
    ),
    CuratedSeason(
        season_year=2026,
        all_star_date=date(2026, 7, 14),
        trade_deadline_date=date(2026, 8, 3),
    ),
)


def load_mlb_seasons(connection: Connection) -> SeasonLoadResult:
    """Upsert documented MLB seasons into curated.season.

    The caller owns the transaction. Exceptions from loading are not
    caught here.
    """
    return load_seasons(connection, MLB_SEASONS)
