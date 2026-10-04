"""Tests for player-season pitching extraction and transformation."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_season_pitching_data import (
    PlayerSeasonPitching,
    PlayerSeasonPitchingGame,
    get_player_season_pitching_games,
    transform_player_season_pitching,
)
from app.core.config import settings


def _game(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    game_id: int = 10,
    batters_faced: int = 1,
    pitches: int = 0,
    hits_allowed: int = 0,
    home_runs_allowed: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
) -> PlayerSeasonPitchingGame:
    return PlayerSeasonPitchingGame(
        player_id=player_id,
        season_id=season_id,
        game_id=game_id,
        batters_faced=batters_faced,
        pitches=pitches,
        hits_allowed=hits_allowed,
        home_runs_allowed=home_runs_allowed,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        strikeouts=strikeouts,
    )


def _row(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    games: int = 1,
    batters_faced: int = 1,
    pitches: int = 0,
    hits_allowed: int = 0,
    home_runs_allowed: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
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


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_player_season_pitching(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_single_player_single_season():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(
                batters_faced=4,
                pitches=15,
                hits_allowed=1,
                walks=1,
                strikeouts=2,
            )
        ],
    )

    assert result == [
        _row(
            batters_faced=4,
            pitches=15,
            hits_allowed=1,
            walks=1,
            strikeouts=2,
        )
    ]


def test_multiple_games_sum_counting_metrics():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(
                game_id=10,
                batters_faced=4,
                pitches=15,
                hits_allowed=1,
                walks=1,
            ),
            _game(
                game_id=11,
                batters_faced=5,
                pitches=18,
                hits_allowed=2,
                home_runs_allowed=1,
                strikeouts=3,
            ),
        ],
    )

    assert result == [
        _row(
            games=2,
            batters_faced=9,
            pitches=33,
            hits_allowed=3,
            home_runs_allowed=1,
            walks=1,
            strikeouts=3,
        )
    ]


def test_multiple_teams_in_one_season_collapse_to_one_row():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(game_id=10, batters_faced=3, pitches=10),
            _game(game_id=11, batters_faced=2, pitches=8, walks=1),
        ],
    )

    assert len(result) == 1
    assert result[0].player_id == 1
    assert result[0].season_id == 2024
    assert result[0].games == 2
    assert result[0].batters_faced == 5
    assert result[0].walks == 1


def test_same_game_multiple_team_rows_count_as_one_game():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(
                game_id=10,
                batters_faced=3,
                pitches=12,
                hits_allowed=1,
                walks=1,
            ),
            _game(
                game_id=10,
                batters_faced=2,
                pitches=7,
                hits_allowed=1,
                home_runs_allowed=1,
            ),
        ],
    )

    assert result == [
        _row(
            games=1,
            batters_faced=5,
            pitches=19,
            hits_allowed=2,
            home_runs_allowed=1,
            walks=1,
        )
    ]


def test_same_player_in_different_seasons_produces_separate_rows():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(season_id=2025, game_id=20, batters_faced=1, strikeouts=1),
            _game(season_id=2024, game_id=10, batters_faced=1, walks=1),
        ],
    )

    assert [row.season_id for row in result] == [2024, 2025]
    assert result[0].walks == 1
    assert result[1].strikeouts == 1


def test_results_are_sorted_by_player_and_season():
    connection = MagicMock()

    result = transform_player_season_pitching(
        connection,
        [
            _game(player_id=2, season_id=2024, game_id=30),
            _game(player_id=1, season_id=2025, game_id=20),
            _game(player_id=1, season_id=2024, game_id=10),
        ],
    )

    assert [(row.player_id, row.season_id) for row in result] == [
        (1, 2024),
        (1, 2025),
        (2, 2024),
    ]


def test_transformation_does_not_manage_transactions():
    connection = MagicMock()

    transform_player_season_pitching(connection, [_game()])

    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


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


def _clear_player_game_pitching(connection: Connection) -> None:
    connection.execute(text("DELETE FROM analytics.player_game_pitching"))


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
    official_game_date: date,
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
            "official_game_date": official_game_date,
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
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game_team (game_id, team_id, home_away)
            VALUES (:game_id, :team_id, :home_away)
            RETURNING game_team_id
            """
        ),
        {"game_id": game_id, "team_id": team_id, "home_away": home_away},
    ).scalar_one()


def _insert_player_game_pitching(
    connection: Connection,
    *,
    pitcher_id: int,
    game_id: int,
    team_id: int,
    batters_faced: int = 1,
    pitches: int = 0,
    hits_allowed: int = 0,
    home_runs_allowed: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_game_pitching (
                pitcher_id,
                game_id,
                team_id,
                batters_faced,
                pitches,
                hits_allowed,
                home_runs_allowed,
                walks,
                hit_by_pitch,
                strikeouts
            )
            VALUES (
                :pitcher_id,
                :game_id,
                :team_id,
                :batters_faced,
                :pitches,
                :hits_allowed,
                :home_runs_allowed,
                :walks,
                :hit_by_pitch,
                :strikeouts
            )
            """
        ),
        {
            "pitcher_id": pitcher_id,
            "game_id": game_id,
            "team_id": team_id,
            "batters_faced": batters_faced,
            "pitches": pitches,
            "hits_allowed": hits_allowed,
            "home_runs_allowed": home_runs_allowed,
            "walks": walks,
            "hit_by_pitch": hit_by_pitch,
            "strikeouts": strikeouts,
        },
    )


def _seed_season_pitching_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    pitcher_mlb_id: int,
    pitcher_team_code: str,
    extra_team_code: str | None = None,
    extra_mlb_game_pk: int | None = None,
    extra_season_year: int | None = None,
) -> dict[str, int]:
    season_id = _insert_season(connection, season_year)
    game_type_id = _insert_game_type(connection, game_type_code, "Zeta Regular")
    game_id = _insert_game(
        connection,
        mlb_game_pk=mlb_game_pk,
        season_id=season_id,
        game_type_id=game_type_id,
        official_game_date=date(season_year, 4, 8),
    )
    player_id = _insert_player(connection, pitcher_mlb_id, "Pat Pitcher")
    team_id = _insert_team(connection, pitcher_team_code, "Zeta Bats")
    _insert_game_team(
        connection,
        game_id=game_id,
        team_id=team_id,
        home_away="AWAY",
    )
    ids = {
        "season_id": season_id,
        "game_id": game_id,
        "player_id": player_id,
        "team_id": team_id,
        "game_type_id": game_type_id,
    }
    if extra_team_code is not None:
        extra_team_id = _insert_team(connection, extra_team_code, "Zeta Aces")
        _insert_game_team(
            connection,
            game_id=game_id,
            team_id=extra_team_id,
            home_away="HOME",
        )
        ids["extra_team_id"] = extra_team_id
    if extra_mlb_game_pk is not None:
        extra_season_id = (
            season_id
            if extra_season_year is None
            else _insert_season(connection, extra_season_year)
        )
        extra_game_id = _insert_game(
            connection,
            mlb_game_pk=extra_mlb_game_pk,
            season_id=extra_season_id,
            game_type_id=game_type_id,
            official_game_date=date(
                extra_season_year or season_year,
                5,
                1,
            ),
        )
        _insert_game_team(
            connection,
            game_id=extra_game_id,
            team_id=team_id,
            home_away="AWAY",
        )
        ids["extra_season_id"] = extra_season_id
        ids["extra_game_id"] = extra_game_id
    return ids


def test_extraction_empty_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_pitching(connection)

            assert get_player_season_pitching_games(connection) == []
    finally:
        engine.dispose()


def test_extraction_joins_game_season_and_maps_pitcher_to_player():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_pitching(connection)
            ids = _seed_season_pitching_lookups(
                connection,
                season_year=2711,
                game_type_code="ZTA",
                mlb_game_pk=951001001,
                pitcher_mlb_id=888091101,
                pitcher_team_code="ZTA",
                extra_team_code="ZTB",
            )
            _insert_player_game_pitching(
                connection,
                pitcher_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                batters_faced=4,
                pitches=15,
                hits_allowed=1,
                walks=1,
            )
            _insert_player_game_pitching(
                connection,
                pitcher_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["extra_team_id"],
                batters_faced=2,
                pitches=8,
                hits_allowed=1,
                home_runs_allowed=1,
            )

            result = get_player_season_pitching_games(connection)

            assert result == [
                PlayerSeasonPitchingGame(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    game_id=ids["game_id"],
                    batters_faced=4,
                    pitches=15,
                    hits_allowed=1,
                    home_runs_allowed=0,
                    walks=1,
                    hit_by_pitch=0,
                    strikeouts=0,
                ),
                PlayerSeasonPitchingGame(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    game_id=ids["game_id"],
                    batters_faced=2,
                    pitches=8,
                    hits_allowed=1,
                    home_runs_allowed=1,
                    walks=0,
                    hit_by_pitch=0,
                    strikeouts=0,
                ),
            ]
    finally:
        engine.dispose()


def test_extraction_maps_multiple_seasons():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_pitching(connection)
            ids = _seed_season_pitching_lookups(
                connection,
                season_year=2712,
                game_type_code="ZTC",
                mlb_game_pk=951001002,
                pitcher_mlb_id=888091201,
                pitcher_team_code="ZTC",
                extra_mlb_game_pk=951001003,
                extra_season_year=2713,
            )
            _insert_player_game_pitching(
                connection,
                pitcher_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                batters_faced=1,
                walks=1,
            )
            _insert_player_game_pitching(
                connection,
                pitcher_id=ids["player_id"],
                game_id=ids["extra_game_id"],
                team_id=ids["team_id"],
                batters_faced=1,
                strikeouts=1,
            )

            result = get_player_season_pitching_games(connection)

            assert [
                (row.season_id, row.game_id, row.walks, row.strikeouts)
                for row in result
            ] == [
                (ids["season_id"], ids["game_id"], 1, 0),
                (ids["extra_season_id"], ids["extra_game_id"], 0, 1),
            ]
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_pitching(connection)
            ids = _seed_season_pitching_lookups(
                connection,
                season_year=2714,
                game_type_code="ZTD",
                mlb_game_pk=951001004,
                pitcher_mlb_id=888091301,
                pitcher_team_code="ZTD",
            )
            _insert_player_game_pitching(
                connection,
                pitcher_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                batters_faced=1,
            )

            original_commit = connection.commit
            original_begin = connection.begin
            commit_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.begin = begin_spy
            try:
                result = get_player_season_pitching_games(connection)
            finally:
                connection.commit = original_commit
                connection.begin = original_begin

            assert len(result) == 1
            commit_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()
