"""Extract and transform game-level pitching into season pitching rows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class PlayerSeasonPitchingGame:
    player_id: int
    season_id: int
    game_id: int
    batters_faced: int
    pitches: int
    hits_allowed: int
    home_runs_allowed: int
    walks: int
    hit_by_pitch: int
    strikeouts: int


@dataclass(frozen=True)
class PlayerSeasonPitching:
    player_id: int
    season_id: int
    games: int
    batters_faced: int
    pitches: int
    hits_allowed: int
    home_runs_allowed: int
    walks: int
    hit_by_pitch: int
    strikeouts: int


def get_player_season_pitching_games(
    connection: Connection,
) -> list[PlayerSeasonPitchingGame]:
    """Return one row per analytics player-game pitching record.

    ``player_id`` is the source ``pitcher_id``. ``season_id`` comes from
    ``curated.game``. Counting statistics are taken from
    ``analytics.player_game_pitching`` and are not re-derived from plate
    appearances. The caller owns the transaction.
    """
    metadata = MetaData()
    player_game_pitching = Table(
        "player_game_pitching",
        metadata,
        schema="analytics",
        autoload_with=connection,
    )
    game = Table(
        "game",
        metadata,
        schema="curated",
        autoload_with=connection,
    )

    statement = (
        select(
            player_game_pitching.c.pitcher_id,
            game.c.season_id,
            player_game_pitching.c.game_id,
            player_game_pitching.c.batters_faced,
            player_game_pitching.c.pitches,
            player_game_pitching.c.hits_allowed,
            player_game_pitching.c.home_runs_allowed,
            player_game_pitching.c.walks,
            player_game_pitching.c.hit_by_pitch,
            player_game_pitching.c.strikeouts,
        )
        .select_from(
            player_game_pitching.join(
                game,
                game.c.game_id == player_game_pitching.c.game_id,
            )
        )
        .order_by(
            player_game_pitching.c.pitcher_id,
            game.c.season_id,
            player_game_pitching.c.game_id,
            player_game_pitching.c.team_id,
        )
    )

    return [
        PlayerSeasonPitchingGame(
            player_id=int(row.pitcher_id),
            season_id=int(row.season_id),
            game_id=int(row.game_id),
            batters_faced=int(row.batters_faced),
            pitches=int(row.pitches),
            hits_allowed=int(row.hits_allowed),
            home_runs_allowed=int(row.home_runs_allowed),
            walks=int(row.walks),
            hit_by_pitch=int(row.hit_by_pitch),
            strikeouts=int(row.strikeouts),
        )
        for row in connection.execute(statement)
    ]


@dataclass
class _Totals:
    game_ids: set[int] = field(default_factory=set)
    batters_faced: int = 0
    pitches: int = 0
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0

    def add(self, game: PlayerSeasonPitchingGame) -> None:
        self.game_ids.add(game.game_id)
        self.batters_faced += game.batters_faced
        self.pitches += game.pitches
        self.hits_allowed += game.hits_allowed
        self.home_runs_allowed += game.home_runs_allowed
        self.walks += game.walks
        self.hit_by_pitch += game.hit_by_pitch
        self.strikeouts += game.strikeouts


def transform_player_season_pitching(
    connection: Connection,
    games: Sequence[PlayerSeasonPitchingGame],
) -> list[PlayerSeasonPitching]:
    """Aggregate game-level pitching into player/season pitching rows.

    Counting statistics are taken from the input. ``games`` is the
    number of distinct source game IDs. The connection is accepted for
    caller consistency and is not queried. The caller owns the
    transaction.
    """
    if not games:
        return []

    totals: dict[tuple[int, int], _Totals] = {}
    for game in games:
        key = (game.player_id, game.season_id)
        current = totals.get(key)
        if current is None:
            current = _Totals()
            totals[key] = current
        current.add(game)

    return [
        PlayerSeasonPitching(
            player_id=player_id,
            season_id=season_id,
            games=len(counts.game_ids),
            batters_faced=counts.batters_faced,
            pitches=counts.pitches,
            hits_allowed=counts.hits_allowed,
            home_runs_allowed=counts.home_runs_allowed,
            walks=counts.walks,
            hit_by_pitch=counts.hit_by_pitch,
            strikeouts=counts.strikeouts,
        )
        for (player_id, season_id), counts in sorted(totals.items())
    ]
