"""Tests for player-season batting extraction and transformation."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_season_batting_data import (
    PlayerSeasonBatting,
    PlayerSeasonBattingGame,
    get_player_season_batting_games,
    transform_player_season_batting,
)
from app.core.config import settings


def _game(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    game_id: int = 10,
    plate_appearances: int = 1,
    at_bats: int = 0,
    hits: int = 0,
    singles: int = 0,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
) -> PlayerSeasonBattingGame:
    return PlayerSeasonBattingGame(
        player_id=player_id,
        season_id=season_id,
        game_id=game_id,
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
    )


def _row(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    games: int = 1,
    plate_appearances: int = 1,
    at_bats: int = 0,
    hits: int = 0,
    singles: int = 0,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
    batting_average: float | None | object = ...,
    on_base_percentage: float | None | object = ...,
    slugging_percentage: float | None | object = ...,
    ops: float | None | object = ...,
    strikeout_rate: float | None | object = ...,
    walk_rate: float | None | object = ...,
) -> PlayerSeasonBatting:
    computed_average = _rate(hits, at_bats)
    computed_obp = _rate(
        hits + walks + hit_by_pitch,
        at_bats + walks + hit_by_pitch + sacrifice_flies,
    )
    computed_slg = _rate(
        singles + (2 * doubles) + (3 * triples) + (4 * home_runs),
        at_bats,
    )
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
        batting_average=(
            computed_average if batting_average is ... else batting_average
        ),
        on_base_percentage=(
            computed_obp if on_base_percentage is ... else on_base_percentage
        ),
        slugging_percentage=(
            computed_slg if slugging_percentage is ... else slugging_percentage
        ),
        ops=(
            (
                None
                if computed_obp is None or computed_slg is None
                else computed_obp + computed_slg
            )
            if ops is ...
            else ops
        ),
        strikeout_rate=(
            _rate(strikeouts, plate_appearances)
            if strikeout_rate is ...
            else strikeout_rate
        ),
        walk_rate=(
            _rate(walks, plate_appearances) if walk_rate is ... else walk_rate
        ),
    )


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_player_season_batting(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_single_player_single_season():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=4,
                at_bats=3,
                hits=1,
                singles=1,
                walks=1,
            )
        ],
    )

    assert result == [
        _row(
            plate_appearances=4,
            at_bats=3,
            hits=1,
            singles=1,
            walks=1,
        )
    ]


def test_multiple_games_sum_counting_metrics():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                game_id=10,
                plate_appearances=4,
                at_bats=3,
                hits=1,
                singles=1,
                walks=1,
            ),
            _game(
                game_id=11,
                plate_appearances=5,
                at_bats=4,
                hits=2,
                doubles=1,
                home_runs=1,
                strikeouts=1,
            ),
        ],
    )

    assert result == [
        _row(
            games=2,
            plate_appearances=9,
            at_bats=7,
            hits=3,
            singles=1,
            doubles=1,
            home_runs=1,
            walks=1,
            strikeouts=1,
        )
    ]


def test_multiple_teams_in_one_season_collapse_to_one_row():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                game_id=10,
                plate_appearances=3,
                at_bats=3,
                hits=1,
                singles=1,
            ),
            _game(
                game_id=11,
                plate_appearances=2,
                at_bats=1,
                walks=1,
            ),
        ],
    )

    assert len(result) == 1
    assert result[0].player_id == 1
    assert result[0].season_id == 2024
    assert result[0].games == 2
    assert result[0].plate_appearances == 5
    assert result[0].walks == 1


def test_same_game_multiple_team_rows_count_as_one_game():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                game_id=10,
                plate_appearances=3,
                at_bats=2,
                hits=1,
                singles=1,
                walks=1,
            ),
            _game(
                game_id=10,
                plate_appearances=2,
                at_bats=2,
                hits=1,
                doubles=1,
            ),
        ],
    )

    assert result == [
        _row(
            games=1,
            plate_appearances=5,
            at_bats=4,
            hits=2,
            singles=1,
            doubles=1,
            walks=1,
        )
    ]


def test_same_player_in_different_seasons_produces_separate_rows():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                season_id=2025,
                game_id=20,
                plate_appearances=1,
                at_bats=1,
                hits=1,
                home_runs=1,
            ),
            _game(
                season_id=2024,
                game_id=10,
                plate_appearances=1,
                at_bats=1,
                hits=1,
                singles=1,
            ),
        ],
    )

    assert [row.season_id for row in result] == [2024, 2025]
    assert result[0].singles == 1
    assert result[1].home_runs == 1


def test_hit_components_aggregate():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                game_id=10,
                plate_appearances=3,
                at_bats=3,
                hits=2,
                singles=1,
                doubles=1,
            ),
            _game(
                game_id=11,
                plate_appearances=3,
                at_bats=3,
                hits=2,
                triples=1,
                home_runs=1,
            ),
        ],
    )

    row = result[0]
    assert row.singles == 1
    assert row.doubles == 1
    assert row.triples == 1
    assert row.home_runs == 1
    assert row.hits == 4
    assert row.hits == row.singles + row.doubles + row.triples + row.home_runs


def test_slugging_uses_total_bases_over_at_bats():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=4,
                at_bats=4,
                hits=4,
                singles=1,
                doubles=1,
                triples=1,
                home_runs=1,
            )
        ],
    )

    total_bases = 1 + (2 * 1) + (3 * 1) + (4 * 1)
    assert result[0].slugging_percentage == total_bases / 4
    assert result[0].slugging_percentage == 2.5


def test_batting_average_is_hits_over_at_bats():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=5,
                at_bats=4,
                hits=1,
                singles=1,
                walks=1,
            )
        ],
    )

    assert result[0].batting_average == 1 / 4


def test_on_base_percentage_uses_official_formula():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=8,
                at_bats=4,
                hits=1,
                singles=1,
                walks=2,
                hit_by_pitch=1,
                sacrifice_flies=1,
                sacrifice_bunts=1,
            )
        ],
    )

    assert result[0].on_base_percentage == (1 + 2 + 1) / (4 + 2 + 1 + 1)
    assert result[0].sacrifice_bunts == 1


def test_ops_is_obp_plus_slg():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=4,
                at_bats=4,
                hits=2,
                singles=1,
                doubles=1,
            )
        ],
    )

    row = result[0]
    assert row.batting_average == 0.5
    assert row.on_base_percentage == 0.5
    assert row.slugging_percentage == 0.75
    assert row.ops == row.on_base_percentage + row.slugging_percentage
    assert row.ops == 1.25


def test_strikeout_rate_is_strikeouts_over_plate_appearances():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=5,
                at_bats=4,
                strikeouts=2,
                walks=1,
            )
        ],
    )

    assert result[0].strikeout_rate == 2 / 5


def test_walk_rate_is_walks_over_plate_appearances():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=5,
                at_bats=4,
                strikeouts=2,
                walks=1,
            )
        ],
    )

    assert result[0].walk_rate == 1 / 5


def test_zero_at_bats_leaves_average_and_slugging_none():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [
            _game(
                plate_appearances=2,
                at_bats=0,
                walks=1,
                sacrifice_flies=1,
            )
        ],
    )

    row = result[0]
    assert row.batting_average is None
    assert row.slugging_percentage is None
    assert row.on_base_percentage == 0.5
    assert row.ops is None


def test_zero_obp_denominator_is_none():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [_game(plate_appearances=1, sacrifice_bunts=1)],
    )

    row = result[0]
    assert row.on_base_percentage is None
    assert row.batting_average is None
    assert row.slugging_percentage is None
    assert row.ops is None


def test_zero_plate_appearances_leave_rates_none():
    connection = MagicMock()

    result = transform_player_season_batting(
        connection,
        [_game(plate_appearances=0)],
    )

    row = result[0]
    assert row.strikeout_rate is None
    assert row.walk_rate is None
    assert row.ops is None


def test_results_are_sorted_by_player_and_season():
    connection = MagicMock()

    result = transform_player_season_batting(
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

    transform_player_season_batting(connection, [_game()])

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


def _clear_player_game_batting(connection: Connection) -> None:
    connection.execute(text("DELETE FROM analytics.player_game_batting"))


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


def _insert_player_game_batting(
    connection: Connection,
    *,
    player_id: int,
    game_id: int,
    team_id: int,
    plate_appearances: int = 1,
    at_bats: int = 0,
    hits: int = 0,
    singles: int = 0,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_game_batting (
                player_id,
                game_id,
                team_id,
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
                :game_id,
                :team_id,
                :plate_appearances,
                :at_bats,
                :hits,
                :singles,
                :doubles,
                :triples,
                :home_runs,
                :walks,
                :hit_by_pitch,
                :strikeouts,
                :sacrifice_flies,
                :sacrifice_bunts
            )
            """
        ),
        {
            "player_id": player_id,
            "game_id": game_id,
            "team_id": team_id,
            "plate_appearances": plate_appearances,
            "at_bats": at_bats,
            "hits": hits,
            "singles": singles,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "walks": walks,
            "hit_by_pitch": hit_by_pitch,
            "strikeouts": strikeouts,
            "sacrifice_flies": sacrifice_flies,
            "sacrifice_bunts": sacrifice_bunts,
        },
    )


def _seed_season_batting_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int,
    batter_team_code: str,
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
    player_id = _insert_player(connection, batter_mlb_id, "Ada Batter")
    team_id = _insert_team(connection, batter_team_code, "Zeta Aces")
    _insert_game_team(
        connection,
        game_id=game_id,
        team_id=team_id,
        home_away="HOME",
    )
    ids = {
        "season_id": season_id,
        "game_id": game_id,
        "player_id": player_id,
        "team_id": team_id,
        "game_type_id": game_type_id,
    }
    if extra_team_code is not None:
        extra_team_id = _insert_team(connection, extra_team_code, "Zeta Bats")
        _insert_game_team(
            connection,
            game_id=game_id,
            team_id=extra_team_id,
            home_away="AWAY",
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
            home_away="HOME",
        )
        ids["extra_season_id"] = extra_season_id
        ids["extra_game_id"] = extra_game_id
    return ids


def test_extraction_empty_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_batting(connection)

            assert get_player_season_batting_games(connection) == []
    finally:
        engine.dispose()


def test_extraction_joins_game_season_and_counting_metrics():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_batting(connection)
            ids = _seed_season_batting_lookups(
                connection,
                season_year=2511,
                game_type_code="ZSA",
                mlb_game_pk=941001001,
                batter_mlb_id=888071101,
                batter_team_code="ZSA",
                extra_team_code="ZSB",
            )
            _insert_player_game_batting(
                connection,
                player_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                plate_appearances=4,
                at_bats=3,
                hits=1,
                singles=1,
                walks=1,
            )
            _insert_player_game_batting(
                connection,
                player_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["extra_team_id"],
                plate_appearances=2,
                at_bats=2,
                hits=1,
                doubles=1,
            )

            result = get_player_season_batting_games(connection)

            assert result == [
                PlayerSeasonBattingGame(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    game_id=ids["game_id"],
                    plate_appearances=4,
                    at_bats=3,
                    hits=1,
                    singles=1,
                    doubles=0,
                    triples=0,
                    home_runs=0,
                    walks=1,
                    hit_by_pitch=0,
                    strikeouts=0,
                    sacrifice_flies=0,
                    sacrifice_bunts=0,
                ),
                PlayerSeasonBattingGame(
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                    game_id=ids["game_id"],
                    plate_appearances=2,
                    at_bats=2,
                    hits=1,
                    singles=0,
                    doubles=1,
                    triples=0,
                    home_runs=0,
                    walks=0,
                    hit_by_pitch=0,
                    strikeouts=0,
                    sacrifice_flies=0,
                    sacrifice_bunts=0,
                ),
            ]
    finally:
        engine.dispose()


def test_extraction_maps_multiple_seasons():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_player_game_batting(connection)
            ids = _seed_season_batting_lookups(
                connection,
                season_year=2512,
                game_type_code="ZSC",
                mlb_game_pk=941001002,
                batter_mlb_id=888071201,
                batter_team_code="ZSC",
                extra_mlb_game_pk=941001003,
                extra_season_year=2513,
            )
            _insert_player_game_batting(
                connection,
                player_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                plate_appearances=1,
                at_bats=1,
                hits=1,
                singles=1,
            )
            _insert_player_game_batting(
                connection,
                player_id=ids["player_id"],
                game_id=ids["extra_game_id"],
                team_id=ids["team_id"],
                plate_appearances=1,
                at_bats=1,
                hits=1,
                home_runs=1,
            )

            result = get_player_season_batting_games(connection)

            assert [
                (row.season_id, row.game_id, row.singles, row.home_runs)
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
            _clear_player_game_batting(connection)
            ids = _seed_season_batting_lookups(
                connection,
                season_year=2514,
                game_type_code="ZSD",
                mlb_game_pk=941001004,
                batter_mlb_id=888071301,
                batter_team_code="ZSD",
            )
            _insert_player_game_batting(
                connection,
                player_id=ids["player_id"],
                game_id=ids["game_id"],
                team_id=ids["team_id"],
                plate_appearances=1,
                at_bats=1,
            )

            original_commit = connection.commit
            original_begin = connection.begin
            commit_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.begin = begin_spy
            try:
                result = get_player_season_batting_games(connection)
            finally:
                connection.commit = original_commit
                connection.begin = original_begin

            assert len(result) == 1
            commit_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()
