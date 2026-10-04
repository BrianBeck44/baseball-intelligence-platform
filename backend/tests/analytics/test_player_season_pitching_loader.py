"""Tests for analytics player-season pitching persistence."""

from contextlib import contextmanager
from dataclasses import asdict
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_season_pitching_data import PlayerSeasonPitching
from app.analytics.player_season_pitching_loader import load_player_season_pitching
from app.core.config import settings


def _row(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    games: int = 1,
    batters_faced: int = 4,
    pitches: int = 15,
    hits_allowed: int = 1,
    home_runs_allowed: int = 0,
    walks: int = 1,
    hit_by_pitch: int = 0,
    strikeouts: int = 1,
) -> PlayerSeasonPitching:
    return PlayerSeasonPitching(
        player_id=player_id,
        season_id=season_id,
        games=games,
        batters_faced=batters_faced,
        pitches=pitches,
        hits_allowed=hits_allowed,
        home_runs_allowed=home_runs_allowed,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        strikeouts=strikeouts,
    )


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


def _seed_season_pitching_load_lookups(
    connection: Connection,
    *,
    player_mlb_id: int,
    season_year: int,
    extra_player_mlb_id: int | None = None,
    extra_season_year: int | None = None,
) -> dict[str, int]:
    ids = {
        "player_id": _insert_player(connection, player_mlb_id, "Pat Pitcher"),
        "season_id": _insert_season(connection, season_year),
    }
    if extra_player_mlb_id is not None:
        ids["extra_player_id"] = _insert_player(
            connection,
            extra_player_mlb_id,
            "Ada Batter",
        )
    if extra_season_year is not None:
        ids["extra_season_id"] = _insert_season(connection, extra_season_year)
    return ids


def _fetch_player_season_pitching(
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
                FROM analytics.player_season_pitching
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def _count_player_season_pitching(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> int:
    return int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_pitching
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        ).scalar_one()
    )


def test_load_empty_input_returns_zero_and_does_not_execute():
    connection = MagicMock()

    result = load_player_season_pitching(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_inserts_a_single_row():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_pitching_load_lookups(
                connection,
                player_mlb_id=888091401,
                season_year=2715,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=2,
                batters_faced=8,
                pitches=31,
                hits_allowed=2,
                home_runs_allowed=1,
                walks=1,
                hit_by_pitch=1,
                strikeouts=3,
            )

            inserted = load_player_season_pitching(connection, [row])
            stored = _fetch_player_season_pitching(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 1
            assert stored["player_id"] == ids["player_id"]
            assert stored["season_id"] == ids["season_id"]
            assert stored["games"] == 2
            assert stored["batters_faced"] == 8
            assert stored["pitches"] == 31
            assert stored["hits_allowed"] == 2
            assert stored["home_runs_allowed"] == 1
            assert stored["walks"] == 1
            assert stored["hit_by_pitch"] == 1
            assert stored["strikeouts"] == 3
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_inserts_multiple_independent_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_pitching_load_lookups(
                connection,
                player_mlb_id=888091501,
                season_year=2716,
                extra_player_mlb_id=888091502,
                extra_season_year=2717,
            )
            rows = [
                _row(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    walks=1,
                ),
                _row(
                    player_id=ids["player_id"],
                    season_id=ids["extra_season_id"],
                    strikeouts=2,
                    home_runs_allowed=1,
                    hits_allowed=1,
                ),
                _row(
                    player_id=ids["extra_player_id"],
                    season_id=ids["season_id"],
                    batters_faced=6,
                    pitches=22,
                ),
            ]

            inserted = load_player_season_pitching(connection, rows)

            assert inserted == 3
            assert (
                _fetch_player_season_pitching(
                    connection,
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                )["walks"]
                == 1
            )
            assert (
                _fetch_player_season_pitching(
                    connection,
                    player_id=ids["player_id"],
                    season_id=ids["extra_season_id"],
                )["strikeouts"]
                == 2
            )
            assert (
                _fetch_player_season_pitching(
                    connection,
                    player_id=ids["extra_player_id"],
                    season_id=ids["season_id"],
                )["pitches"]
                == 22
            )
    finally:
        engine.dispose()


def test_load_does_not_supply_created_at():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_pitching_load_lookups(
                connection,
                player_mlb_id=888091601,
                season_year=2718,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            payload = asdict(row)
            original_execute = connection.execute
            captured: list[object] = []

            def spy_execute(statement, *args, **kwargs):
                captured.append(statement)
                return original_execute(statement, *args, **kwargs)

            connection.execute = spy_execute
            try:
                inserted = load_player_season_pitching(connection, [row])
            finally:
                connection.execute = original_execute

            stored = _fetch_player_season_pitching(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            compiled = str(captured[0].compile(dialect=connection.dialect))

            assert inserted == 1
            assert "created_at" not in payload
            assert "created_at" not in compiled
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_upserts_existing_grain_to_current_metrics():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_pitching_load_lookups(
                connection,
                player_mlb_id=888091701,
                season_year=2719,
            )
            original = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=1,
                batters_faced=4,
                pitches=15,
                hits_allowed=1,
            )
            refreshed = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=2,
                batters_faced=9,
                pitches=33,
                hits_allowed=3,
                home_runs_allowed=1,
                strikeouts=4,
            )

            first = load_player_season_pitching(connection, [original])
            stored_before = _fetch_player_season_pitching(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            second = load_player_season_pitching(connection, [original])
            third = load_player_season_pitching(connection, [refreshed])
            stored_after = _fetch_player_season_pitching(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert first == 1
            assert second == 1
            assert third == 1
            assert (
                _count_player_season_pitching(
                    connection,
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                )
                == 1
            )
            assert stored_after["batters_faced"] == 9
            assert stored_after["pitches"] == 33
            assert stored_after["hits_allowed"] == 3
            assert stored_after["home_runs_allowed"] == 1
            assert stored_after["strikeouts"] == 4
            assert stored_after["created_at"] == stored_before["created_at"]
    finally:
        engine.dispose()


def test_load_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_pitching_load_lookups(
                connection,
                player_mlb_id=888091801,
                season_year=2720,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            original_commit = connection.commit
            original_rollback = connection.rollback
            original_begin = connection.begin
            commit_spy = MagicMock()
            rollback_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.rollback = rollback_spy
            connection.begin = begin_spy
            try:
                inserted = load_player_season_pitching(connection, [row])
            finally:
                connection.commit = original_commit
                connection.rollback = original_rollback
                connection.begin = original_begin

            assert inserted == 1
            commit_spy.assert_not_called()
            rollback_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()
