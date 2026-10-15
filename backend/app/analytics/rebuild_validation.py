"""Source-derived validation for analytics rebuilds."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.analytics.load_all import AnalyticsLoadResult, SeasonLoadResult
from app.analytics.player_game_batting_loader import PlayerGameBattingLoadResult
from app.analytics.player_game_pitching_loader import PlayerGamePitchingLoadResult
from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
)


_REQUIRED_CURATED_SOURCES = (
    "plate_appearance",
    "game",
    "pitch",
)


def require_curated_rebuild_sources(connection: Connection) -> None:
    """Raise ValueError if a required curated source table is empty.

    A full analytics rebuild has no meaningful work without plate
    appearances, games, and pitches. Individual table validators may
    still accept matching zero counts. The caller owns the transaction.
    """
    counts = connection.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM curated.plate_appearance)
                    AS plate_appearance,
                (SELECT COUNT(*) FROM curated.game) AS game,
                (SELECT COUNT(*) FROM curated.pitch) AS pitch
            """
        )
    ).mappings().one()
    empty = [
        f"curated.{table_name}"
        for table_name in _REQUIRED_CURATED_SOURCES
        if int(counts[table_name]) == 0
    ]
    if empty:
        noun = "table is" if len(empty) == 1 else "tables are"
        raise ValueError(
            "Analytics rebuild validation failed: required curated source "
            f"{noun} empty: {', '.join(empty)}"
        )


def validate_analytics_rebuild(
    connection: Connection,
    result: AnalyticsLoadResult,
) -> None:
    """Raise ValueError if rebuilt analytics rows do not match sources."""
    require_curated_rebuild_sources(connection)
    validate_player_game_batting_load(connection, result.game_batting)
    validate_player_game_pitching_load(connection, result.game_pitching)
    validate_player_pitch_type_effectiveness_load(
        connection,
        result.pitch_type_effectiveness,
    )
    validate_player_season_batting_load(connection, result.season_batting)
    validate_player_season_pitching_load(connection, result.season_pitching)


def validate_player_game_batting_load(
    connection: Connection,
    result: PlayerGameBattingLoadResult,
) -> None:
    source = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS plate_appearances,
                COUNT(
                    DISTINCT (batter_id, game_id, batter_team_id)
                ) AS grains
            FROM curated.plate_appearance
            """
        )
    ).mappings().one()
    totals = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(plate_appearances), 0) AS plate_appearances,
                COUNT(*) FILTER (
                    WHERE hits
                        <> singles + doubles + triples + home_runs
                ) AS hits_component_violations,
                COUNT(*) FILTER (
                    WHERE plate_appearances < at_bats
                ) AS pa_below_ab,
                COUNT(*) FILTER (
                    WHERE at_bats < hits
                ) AS ab_below_hits
            FROM analytics.player_game_batting
            """
        )
    ).mappings().one()
    duplicate_grains = _duplicate_grain_count(
        connection,
        """
        SELECT player_id, game_id, team_id
        FROM analytics.player_game_batting
        GROUP BY player_id, game_id, team_id
        HAVING COUNT(*) > 1
        """,
    )
    expected_appearances = int(source["plate_appearances"])
    expected_rows = int(source["grains"])
    _raise_if_mismatched(
        "player_game_batting",
        {
            "extracted": expected_appearances,
            "transformed": expected_rows,
            "loaded": expected_rows,
            "rows": expected_rows,
            "plate_appearances": expected_appearances,
            "hits_component_violations": 0,
            "pa_below_ab": 0,
            "ab_below_hits": 0,
            "duplicate_grains": 0,
        },
        {
            "extracted": result.extracted_count,
            "transformed": result.transformed_count,
            "loaded": result.loaded_count,
            "rows": int(totals["row_count"]),
            "plate_appearances": int(totals["plate_appearances"]),
            "hits_component_violations": int(
                totals["hits_component_violations"]
            ),
            "pa_below_ab": int(totals["pa_below_ab"]),
            "ab_below_hits": int(totals["ab_below_hits"]),
            "duplicate_grains": duplicate_grains,
        },
    )


def validate_player_game_pitching_load(
    connection: Connection,
    result: PlayerGamePitchingLoadResult,
) -> None:
    source = connection.execute(
        text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM curated.plate_appearance
                ) AS plate_appearances,
                (
                    SELECT COUNT(
                        DISTINCT (pitcher_id, game_id, pitcher_team_id)
                    )
                    FROM curated.plate_appearance
                ) AS grains,
                (
                    SELECT COUNT(*)
                    FROM curated.pitch
                ) AS pitches
            """
        )
    ).mappings().one()
    totals = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(batters_faced), 0) AS batters_faced,
                COALESCE(SUM(pitches), 0) AS pitches,
                COUNT(*) FILTER (
                    WHERE home_runs_allowed > hits_allowed
                ) AS home_runs_exceed_hits,
                COUNT(*) FILTER (
                    WHERE hits_allowed > batters_faced
                ) AS hits_exceed_batters_faced,
                COUNT(*) FILTER (
                    WHERE walks > batters_faced
                ) AS walks_exceed_batters_faced,
                COUNT(*) FILTER (
                    WHERE hit_by_pitch > batters_faced
                ) AS hbp_exceed_batters_faced,
                COUNT(*) FILTER (
                    WHERE strikeouts > batters_faced
                ) AS strikeouts_exceed_batters_faced,
                COUNT(*) FILTER (
                    WHERE pitches < batters_faced
                ) AS pitches_below_batters_faced
            FROM analytics.player_game_pitching
            """
        )
    ).mappings().one()
    duplicate_grains = _duplicate_grain_count(
        connection,
        """
        SELECT pitcher_id, game_id, team_id
        FROM analytics.player_game_pitching
        GROUP BY pitcher_id, game_id, team_id
        HAVING COUNT(*) > 1
        """,
    )
    expected_appearances = int(source["plate_appearances"])
    expected_rows = int(source["grains"])
    expected_pitches = int(source["pitches"])
    _raise_if_mismatched(
        "player_game_pitching",
        {
            "extracted": expected_appearances,
            "transformed": expected_rows,
            "loaded": expected_rows,
            "rows": expected_rows,
            "batters_faced": expected_appearances,
            "pitches": expected_pitches,
            "home_runs_exceed_hits": 0,
            "hits_exceed_batters_faced": 0,
            "walks_exceed_batters_faced": 0,
            "hbp_exceed_batters_faced": 0,
            "strikeouts_exceed_batters_faced": 0,
            "pitches_below_batters_faced": 0,
            "duplicate_grains": 0,
        },
        {
            "extracted": result.extracted_count,
            "transformed": result.transformed_count,
            "loaded": result.loaded_count,
            "rows": int(totals["row_count"]),
            "batters_faced": int(totals["batters_faced"]),
            "pitches": int(totals["pitches"]),
            "home_runs_exceed_hits": int(totals["home_runs_exceed_hits"]),
            "hits_exceed_batters_faced": int(totals["hits_exceed_batters_faced"]),
            "walks_exceed_batters_faced": int(
                totals["walks_exceed_batters_faced"]
            ),
            "hbp_exceed_batters_faced": int(totals["hbp_exceed_batters_faced"]),
            "strikeouts_exceed_batters_faced": int(
                totals["strikeouts_exceed_batters_faced"]
            ),
            "pitches_below_batters_faced": int(
                totals["pitches_below_batters_faced"]
            ),
            "duplicate_grains": duplicate_grains,
        },
    )


def validate_player_pitch_type_effectiveness_load(
    connection: Connection,
    result: PlayerPitchTypeEffectivenessLoadResult,
) -> None:
    source = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS typed_pitches,
                COUNT(
                    DISTINCT (plate_appearance.pitcher_id, pitch.pitch_type_id)
                ) AS grains
            FROM curated.pitch
            JOIN curated.plate_appearance
              ON plate_appearance.plate_appearance_id
                  = pitch.plate_appearance_id
            WHERE pitch.pitch_type_id IS NOT NULL
            """
        )
    ).mappings().one()
    totals = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(pitches), 0) AS pitches,
                COUNT(*) FILTER (WHERE whiffs > swings)
                    AS whiffs_exceed_swings,
                COUNT(*) FILTER (WHERE swings > pitches)
                    AS swings_exceed_pitches,
                COUNT(*) FILTER (WHERE balls_in_play > pitches)
                    AS balls_in_play_exceed_pitches,
                COUNT(*) FILTER (WHERE called_strikes > pitches)
                    AS called_strikes_exceed_pitches,
                COUNT(*) FILTER (WHERE fouls > swings)
                    AS fouls_exceed_swings,
                COUNT(*) FILTER (WHERE hits_allowed > balls_in_play)
                    AS hits_exceed_balls_in_play,
                COUNT(*) FILTER (WHERE home_runs_allowed > hits_allowed)
                    AS home_runs_exceed_hits,
                COUNT(*) FILTER (WHERE strikeouts > plate_appearances)
                    AS strikeouts_exceed_plate_appearances,
                COUNT(*) FILTER (WHERE walks > plate_appearances)
                    AS walks_exceed_plate_appearances,
                COUNT(*) FILTER (WHERE hit_by_pitch > plate_appearances)
                    AS hbp_exceed_plate_appearances
            FROM analytics.player_pitch_type_effectiveness
            """
        )
    ).mappings().one()
    rate_violations = connection.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE whiff_rate IS NOT NULL
                      AND (whiff_rate < 0 OR whiff_rate > 1)
                ) AS whiff_rate_out_of_range,
                COUNT(*) FILTER (
                    WHERE called_strike_rate IS NOT NULL
                      AND (
                          called_strike_rate < 0
                          OR called_strike_rate > 1
                      )
                ) AS called_strike_rate_out_of_range,
                COUNT(*) FILTER (
                    WHERE swing_rate IS NOT NULL
                      AND (swing_rate < 0 OR swing_rate > 1)
                ) AS swing_rate_out_of_range,
                COUNT(*) FILTER (
                    WHERE contact_rate IS NOT NULL
                      AND (contact_rate < 0 OR contact_rate > 1)
                ) AS contact_rate_out_of_range,
                COUNT(*) FILTER (
                    WHERE strikeout_rate IS NOT NULL
                      AND (strikeout_rate < 0 OR strikeout_rate > 1)
                ) AS strikeout_rate_out_of_range
            FROM analytics.player_pitch_type_effectiveness
            """
        )
    ).mappings().one()
    duplicate_grains = _duplicate_grain_count(
        connection,
        """
        SELECT player_id, pitch_type_id
        FROM analytics.player_pitch_type_effectiveness
        GROUP BY player_id, pitch_type_id
        HAVING COUNT(*) > 1
        """,
    )
    expected_pitches = int(source["typed_pitches"])
    expected_rows = int(source["grains"])
    expected = {
        "extracted": expected_pitches,
        "transformed": expected_rows,
        "loaded": expected_rows,
        "rows": expected_rows,
        "pitches": expected_pitches,
        "duplicate_grains": 0,
        **{name: 0 for name in totals.keys() if name not in {"row_count", "pitches"}},
        **{name: 0 for name in rate_violations.keys()},
    }
    actual = {
        "extracted": result.extracted_count,
        "transformed": result.transformed_count,
        "loaded": result.loaded_count,
        "rows": int(totals["row_count"]),
        "pitches": int(totals["pitches"]),
        "duplicate_grains": duplicate_grains,
        **{
            name: int(totals[name])
            for name in totals.keys()
            if name not in {"row_count", "pitches"}
        },
        **{name: int(rate_violations[name]) for name in rate_violations.keys()},
    }
    _raise_if_mismatched("player_pitch_type_effectiveness", expected, actual)


def validate_player_season_batting_load(
    connection: Connection,
    result: SeasonLoadResult,
) -> None:
    source = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS game_rows,
                COUNT(DISTINCT (batting.player_id, game.season_id))
                    AS grains,
                COALESCE(SUM(batting.plate_appearances), 0)
                    AS plate_appearances
            FROM analytics.player_game_batting AS batting
            JOIN curated.game AS game
              ON game.game_id = batting.game_id
            """
        )
    ).mappings().one()
    totals = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(plate_appearances), 0) AS plate_appearances
            FROM analytics.player_season_batting
            """
        )
    ).mappings().one()
    duplicate_grains = _duplicate_grain_count(
        connection,
        """
        SELECT player_id, season_id
        FROM analytics.player_season_batting
        GROUP BY player_id, season_id
        HAVING COUNT(*) > 1
        """,
    )
    expected_games = int(source["game_rows"])
    expected_rows = int(source["grains"])
    expected_appearances = int(source["plate_appearances"])
    _raise_if_mismatched(
        "player_season_batting",
        {
            "extracted": expected_games,
            "transformed": expected_rows,
            "loaded": expected_rows,
            "rows": expected_rows,
            "plate_appearances": expected_appearances,
            "duplicate_grains": 0,
        },
        {
            "extracted": result.extracted_count,
            "transformed": result.transformed_count,
            "loaded": result.loaded_count,
            "rows": int(totals["row_count"]),
            "plate_appearances": int(totals["plate_appearances"]),
            "duplicate_grains": duplicate_grains,
        },
    )


def validate_player_season_pitching_load(
    connection: Connection,
    result: SeasonLoadResult,
) -> None:
    source = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS game_rows,
                COUNT(DISTINCT (pitching.pitcher_id, game.season_id))
                    AS grains,
                COALESCE(SUM(pitching.batters_faced), 0) AS batters_faced
            FROM analytics.player_game_pitching AS pitching
            JOIN curated.game AS game
              ON game.game_id = pitching.game_id
            """
        )
    ).mappings().one()
    totals = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(batters_faced), 0) AS batters_faced
            FROM analytics.player_season_pitching
            """
        )
    ).mappings().one()
    duplicate_grains = _duplicate_grain_count(
        connection,
        """
        SELECT player_id, season_id
        FROM analytics.player_season_pitching
        GROUP BY player_id, season_id
        HAVING COUNT(*) > 1
        """,
    )
    expected_games = int(source["game_rows"])
    expected_rows = int(source["grains"])
    expected_batters_faced = int(source["batters_faced"])
    _raise_if_mismatched(
        "player_season_pitching",
        {
            "extracted": expected_games,
            "transformed": expected_rows,
            "loaded": expected_rows,
            "rows": expected_rows,
            "batters_faced": expected_batters_faced,
            "duplicate_grains": 0,
        },
        {
            "extracted": result.extracted_count,
            "transformed": result.transformed_count,
            "loaded": result.loaded_count,
            "rows": int(totals["row_count"]),
            "batters_faced": int(totals["batters_faced"]),
            "duplicate_grains": duplicate_grains,
        },
    )


def _duplicate_grain_count(connection: Connection, grouped_sql: str) -> int:
    return int(
        connection.execute(
            text(f"SELECT COUNT(*) FROM ({grouped_sql}) AS duplicates")
        ).scalar_one()
    )


def _raise_if_mismatched(
    label: str,
    expected: dict[str, int],
    actual: dict[str, int],
) -> None:
    mismatches = [
        f"{name}: expected {expected[name]}, got {actual[name]}"
        for name in expected
        if actual[name] != expected[name]
    ]
    if mismatches:
        raise ValueError(
            f"{label} load validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )
