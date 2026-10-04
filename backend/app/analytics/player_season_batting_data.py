"""Extract and transform game-level batting into season batting rows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class PlayerSeasonBattingGame:
    player_id: int
    season_id: int
    game_id: int
    plate_appearances: int
    at_bats: int
    hits: int
    singles: int
    doubles: int
    triples: int
    home_runs: int
    walks: int
    hit_by_pitch: int
    strikeouts: int
    sacrifice_flies: int
    sacrifice_bunts: int


@dataclass(frozen=True)
class PlayerSeasonBatting:
    player_id: int
    season_id: int
    games: int
    plate_appearances: int
    at_bats: int
    hits: int
    singles: int
    doubles: int
    triples: int
    home_runs: int
    walks: int
    hit_by_pitch: int
    strikeouts: int
    sacrifice_flies: int
    sacrifice_bunts: int
    batting_average: float | None
    on_base_percentage: float | None
    slugging_percentage: float | None
    ops: float | None
    strikeout_rate: float | None
    walk_rate: float | None


def get_player_season_batting_games(
    connection: Connection,
) -> list[PlayerSeasonBattingGame]:
    """Return one row per analytics player-game batting record.

    ``season_id`` comes from ``curated.game``. Counting statistics are
    taken from ``analytics.player_game_batting`` and are not re-derived
    from plate appearances. The caller owns the transaction.
    """
    metadata = MetaData()
    player_game_batting = Table(
        "player_game_batting",
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
            player_game_batting.c.player_id,
            game.c.season_id,
            player_game_batting.c.game_id,
            player_game_batting.c.plate_appearances,
            player_game_batting.c.at_bats,
            player_game_batting.c.hits,
            player_game_batting.c.singles,
            player_game_batting.c.doubles,
            player_game_batting.c.triples,
            player_game_batting.c.home_runs,
            player_game_batting.c.walks,
            player_game_batting.c.hit_by_pitch,
            player_game_batting.c.strikeouts,
            player_game_batting.c.sacrifice_flies,
            player_game_batting.c.sacrifice_bunts,
        )
        .select_from(
            player_game_batting.join(
                game,
                game.c.game_id == player_game_batting.c.game_id,
            )
        )
        .order_by(
            player_game_batting.c.player_id,
            game.c.season_id,
            player_game_batting.c.game_id,
            player_game_batting.c.team_id,
        )
    )

    return [
        PlayerSeasonBattingGame(
            player_id=int(row.player_id),
            season_id=int(row.season_id),
            game_id=int(row.game_id),
            plate_appearances=int(row.plate_appearances),
            at_bats=int(row.at_bats),
            hits=int(row.hits),
            singles=int(row.singles),
            doubles=int(row.doubles),
            triples=int(row.triples),
            home_runs=int(row.home_runs),
            walks=int(row.walks),
            hit_by_pitch=int(row.hit_by_pitch),
            strikeouts=int(row.strikeouts),
            sacrifice_flies=int(row.sacrifice_flies),
            sacrifice_bunts=int(row.sacrifice_bunts),
        )
        for row in connection.execute(statement)
    ]


@dataclass
class _Totals:
    game_ids: set[int] = field(default_factory=set)
    plate_appearances: int = 0
    at_bats: int = 0
    hits: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    sacrifice_flies: int = 0
    sacrifice_bunts: int = 0

    def add(self, game: PlayerSeasonBattingGame) -> None:
        self.game_ids.add(game.game_id)
        self.plate_appearances += game.plate_appearances
        self.at_bats += game.at_bats
        self.hits += game.hits
        self.singles += game.singles
        self.doubles += game.doubles
        self.triples += game.triples
        self.home_runs += game.home_runs
        self.walks += game.walks
        self.hit_by_pitch += game.hit_by_pitch
        self.strikeouts += game.strikeouts
        self.sacrifice_flies += game.sacrifice_flies
        self.sacrifice_bunts += game.sacrifice_bunts


def transform_player_season_batting(
    connection: Connection,
    games: Sequence[PlayerSeasonBattingGame],
) -> list[PlayerSeasonBatting]:
    """Aggregate game-level batting into player/season batting rows.

    Counting statistics are taken from the input. Rates are calculated
    from the season totals. The connection is accepted for caller
    consistency and is not queried. The caller owns the transaction.
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

    rows: list[PlayerSeasonBatting] = []
    for (player_id, season_id), counts in sorted(totals.items()):
        batting_average = _rate(counts.hits, counts.at_bats)
        on_base_percentage = _rate(
            counts.hits + counts.walks + counts.hit_by_pitch,
            counts.at_bats
            + counts.walks
            + counts.hit_by_pitch
            + counts.sacrifice_flies,
        )
        slugging_percentage = _rate(_total_bases(counts), counts.at_bats)
        rows.append(
            PlayerSeasonBatting(
                player_id=player_id,
                season_id=season_id,
                games=len(counts.game_ids),
                plate_appearances=counts.plate_appearances,
                at_bats=counts.at_bats,
                hits=counts.hits,
                singles=counts.singles,
                doubles=counts.doubles,
                triples=counts.triples,
                home_runs=counts.home_runs,
                walks=counts.walks,
                hit_by_pitch=counts.hit_by_pitch,
                strikeouts=counts.strikeouts,
                sacrifice_flies=counts.sacrifice_flies,
                sacrifice_bunts=counts.sacrifice_bunts,
                batting_average=batting_average,
                on_base_percentage=on_base_percentage,
                slugging_percentage=slugging_percentage,
                ops=_ops(on_base_percentage, slugging_percentage),
                strikeout_rate=_rate(
                    counts.strikeouts,
                    counts.plate_appearances,
                ),
                walk_rate=_rate(counts.walks, counts.plate_appearances),
            )
        )
    return rows


def _total_bases(counts: _Totals) -> int:
    return (
        counts.singles
        + (2 * counts.doubles)
        + (3 * counts.triples)
        + (4 * counts.home_runs)
    )


def _ops(
    on_base_percentage: float | None,
    slugging_percentage: float | None,
) -> float | None:
    if on_base_percentage is None or slugging_percentage is None:
        return None
    return on_base_percentage + slugging_percentage


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
