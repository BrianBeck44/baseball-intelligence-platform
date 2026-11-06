"""Tests for player-season CA-OPS extraction and transformation."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_game_batting_data import batting_increments_for
from app.analytics.player_season_batting_data import PlayerSeasonBatting
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.analytics.player_season_ca_ops_data import (
    SHRINKAGE_K,
    PlayerSeasonBattingOps,
    PlayerSeasonCaOps,
    PlayerSeasonCaOpsAppearance,
    _Counts,
    get_player_season_ca_ops_appearances,
    get_player_season_ca_ops_targets,
    transform_player_season_ca_ops,
)
from tests.db import create_test_engine


def _appearance(
    batter_id: int,
    pitcher_id: int,
    season_id: int,
    outcome_code: str | None,
) -> PlayerSeasonCaOpsAppearance:
    return PlayerSeasonCaOpsAppearance(
        batter_id=batter_id,
        pitcher_id=pitcher_id,
        season_id=season_id,
        outcome_code=outcome_code,
    )


def _target(
    player_id: int,
    season_id: int,
    ops: float | None,
) -> PlayerSeasonBattingOps:
    return PlayerSeasonBattingOps(
        player_id=player_id,
        season_id=season_id,
        ops=ops,
    )


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


def test_shrinkage_k_is_one_hundred_fifty():
    assert SHRINKAGE_K == 150


def test_empty_targets_return_empty_list():
    connection = MagicMock()

    result = transform_player_season_ca_ops(
        connection,
        [_appearance(1, 10, 2024, "single")],
        [],
    )

    assert result == []
    connection.execute.assert_not_called()


def test_transform_does_not_query_or_manage_transactions():
    connection = MagicMock()

    transform_player_season_ca_ops(
        connection,
        [_appearance(1, 10, 2024, "single")],
        [_target(1, 2024, 2.0)],
    )

    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_authoritative_batting_outcome_mapping_is_reused(monkeypatch):
    seen: list[str | None] = []
    original = batting_increments_for

    def _wrapped(outcome_code: str | None):
        seen.append(outcome_code)
        return original(outcome_code)

    monkeypatch.setattr(
        "app.analytics.player_season_ca_ops_data.batting_increments_for",
        _wrapped,
    )

    transform_player_season_ca_ops(
        MagicMock(),
        [
            _appearance(1, 10, 2024, "intent_walk"),
            _appearance(1, 10, 2024, None),
            _appearance(1, 11, 2024, "sac_fly_double_play"),
            _appearance(2, 10, 2024, "truncated_pa"),
        ],
        [_target(1, 2024, 0.8), _target(2, 2024, None)],
    )

    assert seen == [
        "intent_walk",
        None,
        "sac_fly_double_play",
        "truncated_pa",
    ]
    assert batting_increments_for("intent_walk") == batting_increments_for("walk")
    assert batting_increments_for("intent_walk").walks == 1
    assert batting_increments_for("intent_walk").at_bats == 0
    assert batting_increments_for(None) == batting_increments_for("catcher_interf")
    assert batting_increments_for(None).at_bats == 0
    assert batting_increments_for("sac_fly_double_play").sacrifice_flies == 1


def test_unknown_outcome_code_raises_value_error():
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="No batting statistic mapping found for outcome code mystery_event",
    ):
        transform_player_season_ca_ops(
            connection,
            [_appearance(1, 10, 2024, "mystery_event")],
            [_target(1, 2024, 0.7)],
        )


def test_target_batter_excluded_from_league_and_pitcher_ops():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 10, 2024, "home_run"),
            _appearance(2, 10, 2024, "field_out"),
            _appearance(2, 11, 2024, "single"),
            _appearance(3, 11, 2024, "double"),
        ],
        [_target(1, 2024, 5.0)],
    )

    league_ops = (2 / 3) + 1
    remaining_pitcher_ops = 0.0
    shrunk = (
        (1 * remaining_pitcher_ops) + (SHRINKAGE_K * league_ops)
    ) / (1 + SHRINKAGE_K)
    row = result[0]

    assert len(result) == 1
    assert row.plate_appearances == 1
    assert row.observed_ops == 5.0
    assert row.league_ops == pytest.approx(league_ops)
    assert row.expected_opponent_ops == pytest.approx(shrunk)
    assert row.ca_ops == pytest.approx(league_ops + (5.0 - shrunk))
    assert row.league_ops != pytest.approx(2.5)
    assert remaining_pitcher_ops != pytest.approx(2.5)


def test_shrinkage_formula_uses_k_one_hundred_fifty():
    connection = MagicMock()
    appearances = [_appearance(1, 10, 2024, "single")]
    appearances.extend(
        _appearance(2, 10, 2024, "field_out") for _ in range(10)
    )
    appearances.extend(_appearance(3, 11, 2024, "single") for _ in range(10))

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 2.0)],
    )

    league_ops = 1.0
    shrunk = (10 * 0.0 + SHRINKAGE_K * league_ops) / (10 + SHRINKAGE_K)
    row = result[0]

    assert SHRINKAGE_K == 150
    assert row.league_ops == pytest.approx(league_ops)
    assert row.expected_opponent_ops == pytest.approx(150 / 160)
    assert row.expected_opponent_ops == pytest.approx(shrunk)
    assert row.ca_ops == pytest.approx(league_ops + (2.0 - shrunk))


def test_expected_opponent_ops_is_weighted_by_batter_pa_counts():
    connection = MagicMock()
    appearances = [
        _appearance(1, 10, 2024, "single"),
        _appearance(1, 10, 2024, "single"),
        _appearance(1, 11, 2024, "single"),
    ]
    appearances.extend(
        _appearance(2, 10, 2024, "field_out") for _ in range(10)
    )
    appearances.extend(_appearance(3, 11, 2024, "single") for _ in range(10))

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 2.0)],
    )

    shrunk_p1 = (10 * 0.0 + 150 * 1.0) / 160
    shrunk_p2 = (10 * 2.0 + 150 * 1.0) / 160
    expected = ((2 * shrunk_p1) + shrunk_p2) / 3
    unweighted = (shrunk_p1 + shrunk_p2) / 2
    row = result[0]

    assert row.plate_appearances == 3
    assert row.expected_opponent_ops == pytest.approx(expected)
    assert row.expected_opponent_ops != pytest.approx(unweighted)


def test_tougher_than_league_opponents_raise_ca_ops_above_observed_ops():
    connection = MagicMock()
    appearances = [_appearance(1, 10, 2024, "single")]
    appearances.extend(
        _appearance(2, 10, 2024, "field_out") for _ in range(10)
    )
    appearances.extend(_appearance(3, 11, 2024, "single") for _ in range(10))

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 2.0)],
    )

    row = result[0]
    assert row.observed_ops == 2.0
    assert row.league_ops == pytest.approx(1.0)
    assert row.expected_opponent_ops is not None
    assert row.ca_ops is not None
    assert row.expected_opponent_ops < row.league_ops
    assert row.ca_ops > row.observed_ops


def test_weaker_than_league_opponents_lower_ca_ops_below_observed_ops():
    connection = MagicMock()
    appearances = [_appearance(1, 10, 2024, "single")]
    appearances.extend(_appearance(2, 10, 2024, "single") for _ in range(10))
    appearances.extend(
        _appearance(3, 11, 2024, "field_out") for _ in range(10)
    )

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 2.0)],
    )

    row = result[0]
    assert row.observed_ops == 2.0
    assert row.league_ops == pytest.approx(1.0)
    assert row.expected_opponent_ops is not None
    assert row.ca_ops is not None
    assert row.expected_opponent_ops > row.league_ops
    assert row.ca_ops < row.observed_ops


def test_leave_one_out_minus_allows_zero_remaining_counts():
    remaining = _Counts(
        plate_appearances=2,
        at_bats=2,
        hits=1,
        singles=1,
        doubles=0,
        triples=0,
        home_runs=0,
        walks=0,
        hit_by_pitch=0,
        sacrifice_flies=0,
    ).minus(
        _Counts(
            plate_appearances=2,
            at_bats=2,
            hits=1,
            singles=1,
        )
    )

    assert remaining.plate_appearances == 0
    assert remaining.at_bats == 0
    assert remaining.hits == 0
    assert remaining.singles == 0
    assert remaining.walks == 0


def test_leave_one_out_minus_rejects_negative_counting_statistics():
    totals = _Counts(
        plate_appearances=2,
        at_bats=1,
        hits=1,
        singles=1,
        walks=0,
    )
    extra_hits = _Counts(
        plate_appearances=1,
        at_bats=1,
        hits=2,
        singles=2,
        walks=0,
    )

    with pytest.raises(ValueError, match="negative hits, singles"):
        totals.minus(extra_hits)


def test_leave_one_out_minus_rejects_negative_plate_appearances():
    with pytest.raises(ValueError, match="negative plate_appearances"):
        _Counts(plate_appearances=1, at_bats=1).minus(
            _Counts(plate_appearances=2, at_bats=1)
        )


def test_ca_ops_equals_observed_ops_when_shrunk_quality_matches_league():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 10, 2024, "single"),
            _appearance(2, 11, 2024, "single"),
            _appearance(3, 11, 2024, "field_out"),
        ],
        [_target(1, 2024, 2.0)],
    )

    row = result[0]
    assert row.league_ops == pytest.approx(1.0)
    assert row.expected_opponent_ops == pytest.approx(1.0)
    assert row.ca_ops == pytest.approx(2.0)
    assert row.ca_ops == pytest.approx(row.observed_ops)


def test_null_ops_and_zero_denominators_remain_null():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 10, 2024, "walk"),
            _appearance(2, 10, 2024, "walk"),
            _appearance(3, 11, 2024, "intent_walk"),
        ],
        [
            _target(1, 2024, None),
            _target(2, 2024, 0.0),
            _target(4, 2024, 0.8),
        ],
    )

    by_player = {row.player_id: row for row in result}
    assert by_player[1].observed_ops is None
    assert by_player[1].league_ops is None
    assert by_player[1].expected_opponent_ops is None
    assert by_player[1].ca_ops is None
    assert by_player[2].league_ops is None
    assert by_player[2].ca_ops is None
    assert by_player[4].plate_appearances == 0
    assert by_player[4].expected_opponent_ops is None
    assert by_player[4].ca_ops is None
    assert 0.0 not in {
        by_player[1].ca_ops,
        by_player[1].league_ops,
        by_player[4].expected_opponent_ops,
    }


def test_null_ca_ops_still_emits_a_result_row():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [],
        [_target(9, 2024, None)],
    )

    assert result == [
        PlayerSeasonCaOps(
            player_id=9,
            season_id=2024,
            plate_appearances=0,
            observed_ops=None,
            league_ops=None,
            expected_opponent_ops=None,
            ca_ops=None,
        )
    ]


def test_null_pitcher_ops_allowed_with_remaining_pas_uses_league_baseline():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 10, 2024, "single"),
            _appearance(2, 10, 2024, "walk"),
            _appearance(3, 11, 2024, "single"),
            _appearance(4, 11, 2024, "field_out"),
        ],
        [_target(1, 2024, 2.0)],
    )

    league_ops = (2 / 3) + 0.5
    row = result[0]
    assert row.league_ops == pytest.approx(league_ops)
    assert row.expected_opponent_ops == pytest.approx(league_ops)
    assert row.ca_ops == pytest.approx(2.0)


def test_pa_only_outcomes_still_weight_matchup_plate_appearances():
    connection = MagicMock()
    appearances = [
        _appearance(1, 10, 2024, "home_run"),
        _appearance(1, 10, 2024, "truncated_pa"),
        _appearance(1, 11, 2024, "catcher_interf"),
        _appearance(1, 11, 2024, None),
    ]
    appearances.extend(
        _appearance(2, 10, 2024, "field_out") for _ in range(10)
    )
    appearances.extend(_appearance(3, 11, 2024, "single") for _ in range(10))

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 5.0)],
    )

    shrunk_p1 = (10 * 0.0 + 150 * 1.0) / 160
    shrunk_p2 = (10 * 2.0 + 150 * 1.0) / 160
    expected_with_pa_only = ((2 * shrunk_p1) + (2 * shrunk_p2)) / 4
    expected_without_pa_only = shrunk_p1
    row = result[0]

    assert row.plate_appearances == 4
    assert row.expected_opponent_ops == pytest.approx(expected_with_pa_only)
    assert row.expected_opponent_ops != pytest.approx(expected_without_pa_only)


def test_league_ops_is_aggregate_not_average_of_pitcher_ops():
    connection = MagicMock()
    appearances = [_appearance(1, 30, 2024, "field_out")]
    appearances.extend(
        _appearance(2, 10, 2024, "field_out") for _ in range(99)
    )
    appearances.append(_appearance(3, 10, 2024, "single"))
    appearances.append(_appearance(4, 11, 2024, "home_run"))

    result = transform_player_season_ca_ops(
        connection,
        appearances,
        [_target(1, 2024, 0.0)],
    )

    aggregate_ops = (2 / 101) + (5 / 101)
    average_of_pitcher_ops = (0.02 + 5.0) / 2
    row = result[0]

    assert row.league_ops == pytest.approx(aggregate_ops)
    assert row.league_ops != pytest.approx(average_of_pitcher_ops)
    assert row.ca_ops == pytest.approx(aggregate_ops + (0.0 - aggregate_ops))


def test_observed_ops_is_taken_from_season_batting_not_recomputed():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 10, 2024, "home_run"),
            _appearance(2, 11, 2024, "single"),
            _appearance(3, 11, 2024, "field_out"),
        ],
        [_target(1, 2024, 0.812345)],
    )

    assert result[0].observed_ops == 0.812345
    assert result[0].observed_ops != pytest.approx(5.0)


def test_first_pitch_pitcher_id_on_the_appearance_is_the_credited_pitcher():
    connection = MagicMock()
    result = transform_player_season_ca_ops(
        connection,
        [
            _appearance(1, 99, 2024, "single"),
            _appearance(2, 11, 2024, "field_out"),
            _appearance(3, 11, 2024, "field_out"),
        ],
        [_target(1, 2024, 2.0)],
    )

    assert result[0].expected_opponent_ops == pytest.approx(0.0)
    assert result[0].ca_ops == pytest.approx(0.0 + (2.0 - 0.0))


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
            "official_game_date": date(2631, 4, 8),
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


def _insert_outcome_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.outcome_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_plate_appearance(
    connection: Connection,
    *,
    game_id: int,
    at_bat_number: int,
    batter_id: int,
    pitcher_id: int,
    batter_team_id: int,
    pitcher_team_id: int,
    outcome_type_id: int | None,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.plate_appearance (
                game_id,
                at_bat_number,
                batter_id,
                pitcher_id,
                batter_team_id,
                pitcher_team_id,
                inning,
                inning_topbot,
                outcome_type_id,
                stand,
                p_throws
            )
            VALUES (
                :game_id,
                :at_bat_number,
                :batter_id,
                :pitcher_id,
                :batter_team_id,
                :pitcher_team_id,
                1,
                'Top',
                :outcome_type_id,
                'L',
                'R'
            )
            RETURNING plate_appearance_id
            """
        ),
        {
            "game_id": game_id,
            "at_bat_number": at_bat_number,
            "batter_id": batter_id,
            "pitcher_id": pitcher_id,
            "batter_team_id": batter_team_id,
            "pitcher_team_id": pitcher_team_id,
            "outcome_type_id": outcome_type_id,
        },
    ).scalar_one()


def _batting_row(player_id: int, season_id: int, ops: float | None) -> PlayerSeasonBatting:
    return PlayerSeasonBatting(
        player_id=player_id,
        season_id=season_id,
        games=1,
        plate_appearances=1,
        at_bats=1,
        hits=1 if ops else 0,
        singles=1 if ops else 0,
        doubles=0,
        triples=0,
        home_runs=0,
        walks=0,
        hit_by_pitch=0,
        strikeouts=0,
        sacrifice_flies=0,
        sacrifice_bunts=0,
        batting_average=1.0 if ops else None,
        on_base_percentage=1.0 if ops else None,
        slugging_percentage=1.0 if ops else None,
        ops=ops,
        strikeout_rate=0.0,
        walk_rate=0.0,
    )


def test_extract_uses_plate_appearance_pitcher_id_and_null_outcomes():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2631)
            game_type_id = _insert_game_type(connection, "ZCA", "Zeta CA-OPS A")
            game_id = _insert_game(
                connection,
                mlb_game_pk=919003001,
                season_id=season_id,
                game_type_id=game_type_id,
            )
            batter_id = _insert_player(connection, 888093001, "CA Batter")
            first_pitcher_id = _insert_player(connection, 888093002, "First Pitcher")
            other_pitcher_id = _insert_player(connection, 888093003, "Other Pitcher")
            batter_team_id = _insert_team(connection, "ZCA", "Zeta CA A")
            pitcher_team_id = _insert_team(connection, "ZCB", "Zeta CA B")
            outcome_type_id = _insert_outcome_type(
                connection,
                "ZCA_SINGLE",
                "Zeta CA Single",
            )
            _insert_plate_appearance(
                connection,
                game_id=game_id,
                at_bat_number=1,
                batter_id=batter_id,
                pitcher_id=first_pitcher_id,
                batter_team_id=batter_team_id,
                pitcher_team_id=pitcher_team_id,
                outcome_type_id=outcome_type_id,
            )
            _insert_plate_appearance(
                connection,
                game_id=game_id,
                at_bat_number=2,
                batter_id=batter_id,
                pitcher_id=first_pitcher_id,
                batter_team_id=batter_team_id,
                pitcher_team_id=pitcher_team_id,
                outcome_type_id=None,
            )

            extracted = [
                row
                for row in get_player_season_ca_ops_appearances(connection)
                if row.batter_id == batter_id
            ]

            assert extracted == [
                PlayerSeasonCaOpsAppearance(
                    batter_id=batter_id,
                    pitcher_id=first_pitcher_id,
                    season_id=season_id,
                    outcome_code="ZCA_SINGLE",
                ),
                PlayerSeasonCaOpsAppearance(
                    batter_id=batter_id,
                    pitcher_id=first_pitcher_id,
                    season_id=season_id,
                    outcome_code=None,
                ),
            ]
            assert all(row.pitcher_id != other_pitcher_id for row in extracted)
    finally:
        engine.dispose()


def test_extract_targets_read_stored_season_batting_ops():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2632)
            player_id = _insert_player(connection, 888093101, "Target Batter")
            load_player_season_batting(
                connection,
                [_batting_row(player_id, season_id, 0.812345)],
            )

            targets = [
                row
                for row in get_player_season_ca_ops_targets(connection)
                if row.player_id == player_id and row.season_id == season_id
            ]

            assert len(targets) == 1
            assert targets[0].player_id == player_id
            assert targets[0].season_id == season_id
            assert targets[0].ops == pytest.approx(0.812345)
    finally:
        engine.dispose()
