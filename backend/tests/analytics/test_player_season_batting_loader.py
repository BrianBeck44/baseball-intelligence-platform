"""Tests for analytics player-season batting persistence."""

from contextlib import contextmanager
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_season_batting_data import PlayerSeasonBatting
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.core.config import settings


def _row(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    games: int = 1,
    plate_appearances: int = 4,
    at_bats: int = 3,
    hits: int = 1,
    singles: int = 1,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 1,
    hit_by_pitch: int = 0,
    strikeouts: int = 1,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
    batting_average: float | None = 1 / 3,
    on_base_percentage: float | None = 0.5,
    slugging_percentage: float | None = 1 / 3,
    ops: float | None = 0.5 + (1 / 3),
    strikeout_rate: float | None = 0.25,
    walk_rate: float | None = 0.25,
) -> PlayerSeasonBatting:
    return PlayerSeasonBatting(
        player_id=player_id,
        season_id=season_id,
        games=games,
        plate_appearances=plate_appearances,
        at_bats=at_bats,
        hits=hits,
        singles=singles,
        doubles=doubles,
        triples=triples,
        home_runs=home_runs,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        strikeouts=strikeouts,
        sacrifice_flies=sacrifice_flies,
        sacrifice_bunts=sacrifice_bunts,
        batting_average=batting_average,
        on_base_percentage=on_base_percentage,
        slugging_percentage=slugging_percentage,
        ops=ops,
        strikeout_rate=strikeout_rate,
        walk_rate=walk_rate,
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


def _seed_season_batting_load_lookups(
    connection: Connection,
    *,
    player_mlb_id: int,
    season_year: int,
    extra_player_mlb_id: int | None = None,
    extra_season_year: int | None = None,
) -> dict[str, int]:
    ids = {
        "player_id": _insert_player(connection, player_mlb_id, "Ada Batter"),
        "season_id": _insert_season(connection, season_year),
    }
    if extra_player_mlb_id is not None:
        ids["extra_player_id"] = _insert_player(
            connection,
            extra_player_mlb_id,
            "Pat Pitcher",
        )
    if extra_season_year is not None:
        ids["extra_season_id"] = _insert_season(connection, extra_season_year)
    return ids


def _fetch_player_season_batting(
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
                FROM analytics.player_season_batting
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def _count_player_season_batting(
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
                FROM analytics.player_season_batting
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        ).scalar_one()
    )


def _as_rate(value: object) -> float | None:
    return None if value is None else float(value)


def test_load_empty_input_returns_zero_and_does_not_execute():
    connection = MagicMock()

    result = load_player_season_batting(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_inserts_a_single_row():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081101,
                season_year=2611,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=2,
                plate_appearances=8,
                at_bats=6,
                hits=2,
                singles=1,
                doubles=1,
                triples=0,
                home_runs=0,
                walks=1,
                hit_by_pitch=1,
                strikeouts=2,
                sacrifice_flies=0,
                sacrifice_bunts=0,
                batting_average=1 / 3,
                on_base_percentage=0.5,
                slugging_percentage=0.5,
                ops=1.0,
                strikeout_rate=0.25,
                walk_rate=0.125,
            )

            inserted = load_player_season_batting(connection, [row])
            stored = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 1
            assert stored["player_id"] == ids["player_id"]
            assert stored["season_id"] == ids["season_id"]
            assert stored["games"] == 2
            assert stored["plate_appearances"] == 8
            assert stored["at_bats"] == 6
            assert stored["hits"] == 2
            assert stored["singles"] == 1
            assert stored["doubles"] == 1
            assert stored["triples"] == 0
            assert stored["home_runs"] == 0
            assert stored["walks"] == 1
            assert stored["hit_by_pitch"] == 1
            assert stored["strikeouts"] == 2
            assert stored["sacrifice_flies"] == 0
            assert stored["sacrifice_bunts"] == 0
            assert _as_rate(stored["batting_average"]) == pytest.approx(1 / 3)
            assert _as_rate(stored["on_base_percentage"]) == pytest.approx(0.5)
            assert _as_rate(stored["slugging_percentage"]) == pytest.approx(0.5)
            assert _as_rate(stored["ops"]) == pytest.approx(1.0)
            assert _as_rate(stored["strikeout_rate"]) == pytest.approx(0.25)
            assert _as_rate(stored["walk_rate"]) == pytest.approx(0.125)
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_inserts_multiple_independent_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081201,
                season_year=2612,
                extra_player_mlb_id=888081202,
                extra_season_year=2613,
            )
            rows = [
                _row(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    hits=1,
                    singles=1,
                    batting_average=1 / 3,
                    slugging_percentage=1 / 3,
                    ops=0.5 + (1 / 3),
                ),
                _row(
                    player_id=ids["player_id"],
                    season_id=ids["extra_season_id"],
                    hits=2,
                    doubles=1,
                    home_runs=1,
                    batting_average=2 / 3,
                    slugging_percentage=2.0,
                    ops=0.5 + 2.0,
                ),
                _row(
                    player_id=ids["extra_player_id"],
                    season_id=ids["season_id"],
                    hits=0,
                    singles=0,
                    batting_average=0.0,
                    slugging_percentage=0.0,
                    ops=0.5,
                    strikeout_rate=0.5,
                ),
            ]

            inserted = load_player_season_batting(connection, rows)
            first = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            second = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["extra_season_id"],
            )
            third = _fetch_player_season_batting(
                connection,
                player_id=ids["extra_player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 3
            assert first["hits"] == 1
            assert second["home_runs"] == 1
            assert third["strikeout_rate"] is not None
            assert _as_rate(third["strikeout_rate"]) == pytest.approx(0.5)
    finally:
        engine.dispose()


def test_load_does_not_supply_created_at():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081301,
                season_year=2614,
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
                inserted = load_player_season_batting(connection, [row])
            finally:
                connection.execute = original_execute

            stored = _fetch_player_season_batting(
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
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081401,
                season_year=2615,
            )
            original = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=1,
                plate_appearances=4,
                at_bats=4,
                hits=1,
                singles=1,
                batting_average=0.25,
                on_base_percentage=0.25,
                slugging_percentage=0.25,
                ops=0.5,
                strikeout_rate=0.25,
                walk_rate=0.0,
                walks=0,
                strikeouts=1,
            )
            refreshed = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=2,
                plate_appearances=8,
                at_bats=8,
                hits=4,
                singles=1,
                doubles=1,
                home_runs=2,
                batting_average=0.5,
                on_base_percentage=0.5,
                slugging_percentage=1.375,
                ops=1.875,
                strikeout_rate=0.125,
                walk_rate=0.0,
                walks=0,
                strikeouts=1,
            )

            first = load_player_season_batting(connection, [original])
            stored_before = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            second = load_player_season_batting(connection, [original])
            stored_same = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            third = load_player_season_batting(connection, [refreshed])
            stored_after = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert first == 1
            assert second == 1
            assert third == 1
            assert (
                _count_player_season_batting(
                    connection,
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                )
                == 1
            )
            assert stored_same["hits"] == 1
            assert stored_after["hits"] == 4
            assert stored_after["games"] == 2
            assert _as_rate(stored_after["batting_average"]) == pytest.approx(0.5)
            assert _as_rate(stored_after["slugging_percentage"]) == pytest.approx(
                1.375
            )
            assert _as_rate(stored_after["ops"]) == pytest.approx(1.875)
            assert stored_after["created_at"] == stored_before["created_at"]
    finally:
        engine.dispose()


def test_load_persists_null_rates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081501,
                season_year=2616,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                games=1,
                plate_appearances=0,
                at_bats=0,
                hits=0,
                singles=0,
                walks=0,
                strikeouts=0,
                batting_average=None,
                on_base_percentage=None,
                slugging_percentage=None,
                ops=None,
                strikeout_rate=None,
                walk_rate=None,
            )

            inserted = load_player_season_batting(connection, [row])
            stored = _fetch_player_season_batting(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 1
            assert stored["batting_average"] is None
            assert stored["on_base_percentage"] is None
            assert stored["slugging_percentage"] is None
            assert stored["ops"] is None
            assert stored["strikeout_rate"] is None
            assert stored["walk_rate"] is None
    finally:
        engine.dispose()


def test_load_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_season_batting_load_lookups(
                connection,
                player_mlb_id=888081601,
                season_year=2617,
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
                inserted = load_player_season_batting(connection, [row])
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
