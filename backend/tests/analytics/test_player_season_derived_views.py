"""Tests for player-season derived batting and pitching views."""

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings


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


def _insert_season(connection: Connection, season_year: int) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.season (season_year)
            VALUES (:season_year)
            RETURNING season_id
            """
        ),
        {"season_year": season_year},
    ).scalar_one()


def _insert_player(connection: Connection, mlb_player_id: int, full_name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.player (mlb_player_id, full_name)
            VALUES (:mlb_player_id, :full_name)
            RETURNING player_id
            """
        ),
        {"mlb_player_id": mlb_player_id, "full_name": full_name},
    ).scalar_one()


def _insert_player_season_batting(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    at_bats: int,
    hits: int,
    singles: int,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    plate_appearances: int | None = None,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_season_batting (
                player_id,
                season_id,
                games,
                plate_appearances,
                at_bats,
                hits,
                singles,
                doubles,
                triples,
                home_runs,
                walks,
                hit_by_pitch,
                strikeouts,
                sacrifice_flies,
                sacrifice_bunts
            )
            VALUES (
                :player_id,
                :season_id,
                1,
                :plate_appearances,
                :at_bats,
                :hits,
                :singles,
                :doubles,
                :triples,
                :home_runs,
                0,
                0,
                0,
                0,
                0
            )
            """
        ),
        {
            "player_id": player_id,
            "season_id": season_id,
            "plate_appearances": (
                plate_appearances
                if plate_appearances is not None
                else at_bats
            ),
            "at_bats": at_bats,
            "hits": hits,
            "singles": singles,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
        },
    )


def _insert_player_season_pitching(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    batters_faced: int,
    walks: int = 0,
    strikeouts: int = 0,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_season_pitching (
                player_id,
                season_id,
                games,
                batters_faced,
                pitches,
                hits_allowed,
                home_runs_allowed,
                walks,
                hit_by_pitch,
                strikeouts
            )
            VALUES (
                :player_id,
                :season_id,
                1,
                :batters_faced,
                :batters_faced,
                0,
                0,
                :walks,
                0,
                :strikeouts
            )
            """
        ),
        {
            "player_id": player_id,
            "season_id": season_id,
            "batters_faced": batters_faced,
            "walks": walks,
            "strikeouts": strikeouts,
        },
    )


def _fetch_batting_derived(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
):
    return (
        connection.execute(
            text(
                """
                SELECT *
                FROM analytics.v_player_season_batting_derived
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def _fetch_pitching_rates(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
):
    return (
        connection.execute(
            text(
                """
                SELECT *
                FROM analytics.v_player_season_pitching_rates
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def test_batting_view_matches_source_grain_and_formulas():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888092101, "Ada Batter")
            season_id = _insert_season(connection, 2801)
            _insert_player_season_batting(
                connection,
                player_id=player_id,
                season_id=season_id,
                at_bats=4,
                hits=3,
                singles=1,
                doubles=1,
                home_runs=1,
            )

            derived = _fetch_batting_derived(
                connection,
                player_id=player_id,
                season_id=season_id,
            )
            source_count = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM analytics.player_season_batting")
                ).scalar_one()
            )
            view_count = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM analytics.v_player_season_batting_derived
                        """
                    )
                ).scalar_one()
            )
            duplicate_grains = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT player_id, season_id
                            FROM analytics.v_player_season_batting_derived
                            GROUP BY player_id, season_id
                            HAVING COUNT(*) > 1
                        ) AS duplicates
                        """
                    )
                ).scalar_one()
            )

            assert derived["player_id"] == player_id
            assert derived["season_id"] == season_id
            assert derived["player_id"] is not None
            assert derived["season_id"] is not None
            assert "team_id" not in derived
            assert derived["extra_base_hits"] == 2
            assert derived["total_bases"] == 7
            assert float(derived["isolated_power"]) == pytest.approx((7 - 3) / 4)
            assert view_count == source_count
            assert duplicate_grains == 0
    finally:
        engine.dispose()


def test_batting_view_zero_at_bats_leaves_isolated_power_null():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888092102, "Pat Walker")
            season_id = _insert_season(connection, 2802)
            _insert_player_season_batting(
                connection,
                player_id=player_id,
                season_id=season_id,
                at_bats=0,
                hits=0,
                singles=0,
                plate_appearances=1,
            )

            derived = _fetch_batting_derived(
                connection,
                player_id=player_id,
                season_id=season_id,
            )

            assert derived["extra_base_hits"] == 0
            assert derived["total_bases"] == 0
            assert derived["isolated_power"] is None
    finally:
        engine.dispose()


def test_pitching_view_matches_source_grain_and_formulas():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888092201, "Pat Pitcher")
            season_id = _insert_season(connection, 2803)
            _insert_player_season_pitching(
                connection,
                player_id=player_id,
                season_id=season_id,
                batters_faced=20,
                walks=4,
                strikeouts=8,
            )

            derived = _fetch_pitching_rates(
                connection,
                player_id=player_id,
                season_id=season_id,
            )
            source_count = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM analytics.player_season_pitching"
                    )
                ).scalar_one()
            )
            view_count = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM analytics.v_player_season_pitching_rates
                        """
                    )
                ).scalar_one()
            )
            duplicate_grains = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT player_id, season_id
                            FROM analytics.v_player_season_pitching_rates
                            GROUP BY player_id, season_id
                            HAVING COUNT(*) > 1
                        ) AS duplicates
                        """
                    )
                ).scalar_one()
            )

            assert derived["player_id"] == player_id
            assert derived["season_id"] == season_id
            assert derived["player_id"] is not None
            assert derived["season_id"] is not None
            assert "team_id" not in derived
            assert float(derived["strikeout_rate"]) == pytest.approx(8 / 20)
            assert float(derived["walk_rate"]) == pytest.approx(4 / 20)
            assert float(derived["strikeout_to_walk_ratio"]) == pytest.approx(8 / 4)
            assert view_count == source_count
            assert duplicate_grains == 0
    finally:
        engine.dispose()


def test_pitching_view_zero_denominators_are_null():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888092202, "Ada Reliever")
            empty_season_id = _insert_season(connection, 2804)
            no_walk_season_id = _insert_season(connection, 2805)
            _insert_player_season_pitching(
                connection,
                player_id=player_id,
                season_id=empty_season_id,
                batters_faced=0,
                walks=0,
                strikeouts=0,
            )
            _insert_player_season_pitching(
                connection,
                player_id=player_id,
                season_id=no_walk_season_id,
                batters_faced=10,
                walks=0,
                strikeouts=3,
            )

            empty = _fetch_pitching_rates(
                connection,
                player_id=player_id,
                season_id=empty_season_id,
            )
            no_walks = _fetch_pitching_rates(
                connection,
                player_id=player_id,
                season_id=no_walk_season_id,
            )

            assert empty["strikeout_rate"] is None
            assert empty["walk_rate"] is None
            assert empty["strikeout_to_walk_ratio"] is None
            assert float(no_walks["strikeout_rate"]) == pytest.approx(3 / 10)
            assert float(no_walks["walk_rate"]) == pytest.approx(0)
            assert no_walks["strikeout_to_walk_ratio"] is None
    finally:
        engine.dispose()
