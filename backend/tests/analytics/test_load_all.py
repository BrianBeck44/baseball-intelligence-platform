"""Tests for analytics rebuild orchestration."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.load_all import (
    AnalyticsLoadResult,
    SeasonLoadResult,
    _ANALYTICS_CLEAR_ORDER,
    clear_analytics_tables,
    load_all_analytics,
)
from app.analytics.player_game_batting_data import (
    PlayerGameBatting,
    load_player_game_batting,
)
from app.analytics.player_game_batting_loader import PlayerGameBattingLoadResult
from app.analytics.player_game_pitching_loader import PlayerGamePitchingLoadResult
from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
)
from tests.db import create_test_engine


def _create_engine() -> Engine:
    return create_test_engine()


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


def _insert_game_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_game(
    connection: Connection,
    *,
    mlb_game_pk: int,
    season_id: int,
    game_type_id: int,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game (
                mlb_game_pk,
                season_id,
                official_game_date,
                game_type_id
            )
            VALUES (
                :mlb_game_pk,
                :season_id,
                :official_game_date,
                :game_type_id
            )
            RETURNING game_id
            """
        ),
        {
            "mlb_game_pk": mlb_game_pk,
            "season_id": season_id,
            "official_game_date": date(2299, 4, 8),
            "game_type_id": game_type_id,
        },
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


def _insert_team(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.team (code, name)
            VALUES (:code, :name)
            RETURNING team_id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_game_team(
    connection: Connection,
    *,
    game_id: int,
    team_id: int,
    home_away: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO curated.game_team (game_id, team_id, home_away)
            VALUES (:game_id, :team_id, :home_away)
            """
        ),
        {"game_id": game_id, "team_id": team_id, "home_away": home_away},
    )


def _batting_row(player_id: int, game_id: int, team_id: int) -> PlayerGameBatting:
    return PlayerGameBatting(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        plate_appearances=2,
        at_bats=2,
        hits=1,
        singles=1,
        doubles=0,
        triples=0,
        home_runs=0,
        walks=0,
        hit_by_pitch=0,
        strikeouts=0,
        sacrifice_flies=0,
        sacrifice_bunts=0,
    )


def _seed_batting_lookups(connection: Connection) -> dict[str, int]:
    season_id = _insert_season(connection, 2299)
    game_type_id = _insert_game_type(connection, "ZRA", "Zeta Rebuild")
    game_id = _insert_game(
        connection,
        mlb_game_pk=919001001,
        season_id=season_id,
        game_type_id=game_type_id,
    )
    batter_id = _insert_player(connection, 888091101, "Rebuild Batter")
    leftover_id = _insert_player(connection, 888091199, "Leftover Batter")
    team_id = _insert_team(connection, "ZRA", "Zeta Rebuild A")
    other_team_id = _insert_team(connection, "ZRB", "Zeta Rebuild B")
    _insert_game_team(
        connection,
        game_id=game_id,
        team_id=team_id,
        home_away="HOME",
    )
    _insert_game_team(
        connection,
        game_id=game_id,
        team_id=other_team_id,
        home_away="AWAY",
    )
    return {
        "game_id": game_id,
        "batter_id": batter_id,
        "leftover_id": leftover_id,
        "team_id": team_id,
    }


def test_clear_analytics_tables_uses_reverse_dependency_order():
    connection = MagicMock()

    clear_analytics_tables(connection)

    statements = [
        str(call.args[0])
        for call in connection.execute.call_args_list
    ]
    assert all(
        f"DELETE FROM analytics.{name}" in statements[index]
        for index, name in enumerate(_ANALYTICS_CLEAR_ORDER)
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_all_analytics_clears_then_loads_in_dependency_order():
    connection = MagicMock()
    game_batting = PlayerGameBattingLoadResult(3, 2, 2)
    game_pitching = PlayerGamePitchingLoadResult(3, 1, 1)
    effectiveness = PlayerPitchTypeEffectivenessLoadResult(4, 2, 2)
    season_batting_games = [object(), object()]
    season_batting_rows = [object()]
    season_pitching_games = [object()]
    season_pitching_rows = [object()]
    order: list[str] = []

    def track(name: str, return_value):
        def _call(*_args, **_kwargs):
            order.append(name)
            return return_value

        return _call

    with (
        patch(
            "app.analytics.load_all.clear_analytics_tables",
            side_effect=track("clear", None),
        ),
        patch(
            "app.analytics.load_all.load_player_game_batting_from_curated",
            side_effect=track("game_batting", game_batting),
        ),
        patch(
            "app.analytics.load_all.load_player_game_pitching_from_curated",
            side_effect=track("game_pitching", game_pitching),
        ),
        patch(
            "app.analytics.load_all.load_player_pitch_type_effectiveness_from_curated",
            side_effect=track("effectiveness", effectiveness),
        ),
        patch(
            "app.analytics.load_all.get_player_season_batting_games",
            side_effect=track("season_batting_extract", season_batting_games),
        ),
        patch(
            "app.analytics.load_all.transform_player_season_batting",
            side_effect=track("season_batting_transform", season_batting_rows),
        ),
        patch(
            "app.analytics.load_all.load_player_season_batting",
            side_effect=track("season_batting_load", 1),
        ),
        patch(
            "app.analytics.load_all.get_player_season_pitching_games",
            side_effect=track("season_pitching_extract", season_pitching_games),
        ),
        patch(
            "app.analytics.load_all.transform_player_season_pitching",
            side_effect=track("season_pitching_transform", season_pitching_rows),
        ),
        patch(
            "app.analytics.load_all.load_player_season_pitching",
            side_effect=track("season_pitching_load", 1),
        ),
    ):
        result = load_all_analytics(connection)

    assert order == [
        "clear",
        "game_batting",
        "game_pitching",
        "effectiveness",
        "season_batting_extract",
        "season_batting_transform",
        "season_batting_load",
        "season_pitching_extract",
        "season_pitching_transform",
        "season_pitching_load",
    ]
    assert result == AnalyticsLoadResult(
        game_batting=game_batting,
        game_pitching=game_pitching,
        pitch_type_effectiveness=effectiveness,
        season_batting=SeasonLoadResult(2, 1, 1),
        season_pitching=SeasonLoadResult(1, 1, 1),
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_clear_then_reload_replaces_existing_analytics_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_lookups(connection)
            leftover = _batting_row(
                ids["leftover_id"],
                ids["game_id"],
                ids["team_id"],
            )
            kept = _batting_row(
                ids["batter_id"],
                ids["game_id"],
                ids["team_id"],
            )
            load_player_game_batting(connection, [leftover, kept])

            def _row_count() -> int:
                return int(
                    connection.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM analytics.player_game_batting
                            WHERE game_id = :game_id
                            """
                        ),
                        {"game_id": ids["game_id"]},
                    ).scalar_one()
                )

            assert _row_count() == 2
            clear_analytics_tables(connection)
            assert _row_count() == 0
            load_player_game_batting(connection, [kept])
            assert _row_count() == 1
            leftover_count = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM analytics.player_game_batting
                        WHERE player_id = :player_id
                        """
                    ),
                    {"player_id": ids["leftover_id"]},
                ).scalar_one()
            )
            assert leftover_count == 0
            clear_analytics_tables(connection)
            load_player_game_batting(connection, [kept])
            assert _row_count() == 1
    finally:
        engine.dispose()
