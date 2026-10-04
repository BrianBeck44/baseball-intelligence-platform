# ADR-004: Player Season Batting Analytics

**Status:** Proposed
**Date:** 2026-10-03
**Decision Type:** Analytics / Data Modeling

## Context

The Baseball Intelligence Platform now has an authoritative curated event layer and three analytics tables:

```text
analytics.player_game_batting
analytics.player_game_pitching
analytics.player_pitch_type_effectiveness
```

`analytics.player_game_batting` already materializes one batting line per player, game, and batting team from curated plate appearances.

The next capability is a season-level batting surface that can support:

* batting-average analysis
* on-base analysis
* slugging analysis
* OPS
* strikeout and walk rates
* player performance trends
* later rolling and advanced batting analytics

The proposed table is:

```text
analytics.player_season_batting
```

This table must not become a second source of truth for plate-appearance outcomes. It aggregates existing player-game batting facts and attaches season identity from the existing game relationship.

---

## Decision

Create `analytics.player_season_batting` at the following analytical grain:

```text
(player_id, season_id)
```

Each row is one batter's season batting line across all teams.

`analytics.player_game_batting` is the authoritative source for season-level batting counting metrics.

`curated.game.season_id` supplies the season dimension.

Counting metrics are not re-derived from `curated.plate_appearance`. Re-deriving those facts would duplicate the game-level outcome rules and risk silent drift.

Season identity will not be copied onto `analytics.player_game_batting`. The existing `curated.game.season_id` relationship is sufficient.

---

# Data Flow

The analytics layer remains derived:

```text
RAW
 ↓
CURATED
 ↓
analytics.player_game_batting
 ↓
analytics.player_season_batting
```

More specifically:

```text
RAW Statcast
 ↓
curated.plate_appearance / curated.game
 ↓
analytics.player_game_batting
 ↓
analytics.player_season_batting
```

`curated.plate_appearance` is the source of the already-built game-level batting facts.

`curated.game` is used only to resolve `season_id` from `analytics.player_game_batting.game_id`.

The first season-batting implementation must not query raw Statcast and must not re-aggregate `curated.plate_appearance`.

---

# Analytical Grain

The table grain is:

```text
(player_id, season_id)
```

There is exactly one row per player per season. All teams are combined.

Examples:

```text
Player A + 2024
Player A + 2025
Player B + 2025
```

The first version will not include:

```text
team_id
game_id
game_type_id
```

A player who bats for multiple teams in the same season still produces one season row. Team splits can be introduced later as a separate grain.

A player who has two `player_game_batting` rows in the same game, because the game-level grain includes `team_id`, still counts as one game at season level.

The first version includes every game already present in `analytics.player_game_batting`. It does not filter by game type.

---

# Source Mapping

Extraction reads one source row per `analytics.player_game_batting` record and attaches `curated.game.season_id`.

Required join:

```text
analytics.player_game_batting
    JOIN curated.game
      ON curated.game.game_id = analytics.player_game_batting.game_id
```

No join to `curated.player` or `curated.season` is required during extraction. Foreign keys on the analytics table will enforce those relationships at load time.

Every source row must have a non-null `season_id`. A missing game or season relationship is an integrity error, not a row to skip.

---

# Source Semantics

Season counting metrics inherit the definitions already implemented by `analytics.player_game_batting`. Those definitions are not restated as new baseball rules. They are documented here so the season table does not invent a second meaning.

The game-level grain is:

```text
(player_id, game_id, team_id)
```

Each curated plate appearance increments `plate_appearances` by 1 for that grain, including `catcher_interf`, `truncated_pa`, and `NULL` outcomes.

The current increment matrix is:

| Outcome                 | PA | AB |  H | 1B | 2B | 3B | HR | BB | HBP |  K | SF | SH |
| ----------------------- | -: | -: | -: | -: | -: | -: | -: | -: | --: | -: | -: | -: |
| `single`                |  1 |  1 |  1 |  1 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `double`                |  1 |  1 |  1 |  0 |  1 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `triple`                |  1 |  1 |  1 |  0 |  0 |  1 |  0 |  0 |   0 |  0 |  0 |  0 |
| `home_run`              |  1 |  1 |  1 |  0 |  0 |  0 |  1 |  0 |   0 |  0 |  0 |  0 |
| `walk`                  |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  1 |   0 |  0 |  0 |  0 |
| `intent_walk`           |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  1 |   0 |  0 |  0 |  0 |
| `hit_by_pitch`          |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   1 |  0 |  0 |  0 |
| `strikeout`             |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  1 |  0 |  0 |
| `strikeout_double_play` |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  1 |  0 |  0 |
| `sac_fly`               |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  1 |  0 |
| `sac_bunt`              |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  1 |
| `field_out`             |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `field_error`           |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `force_out`             |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `grounded_into_double_play` |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `double_play`           |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `fielders_choice`       |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `fielders_choice_out`   |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `catcher_interf`        |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `truncated_pa`          |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `NULL` outcome          |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |

Unknown non-null outcome codes raise `ValueError` at the game-level transform. The season table does not introduce a second outcome mapper.

## Inherited counting definitions

### `games`

`analytics.player_game_batting` does not store a games column.

Season `games` is therefore:

```text
COUNT(DISTINCT game_id)
```

from the player's game-level batting rows in that season.

This is not `COUNT(*)` of source rows. One game can produce more than one `player_game_batting` row because the source grain includes `team_id`.

### `plate_appearances`

```text
SUM(analytics.player_game_batting.plate_appearances)
```

Every source plate appearance is counted, including catcher interference, truncated plate appearances, and NULL outcomes.

### `at_bats`

```text
SUM(analytics.player_game_batting.at_bats)
```

At-bats exclude walks, intentional walks, hit by pitch, sacrifice flies, sacrifice bunts, catcher interference, truncated plate appearances, and NULL outcomes.

### `hits`

```text
SUM(analytics.player_game_batting.hits)
```

A hit is a `single`, `double`, `triple`, or `home_run`. Fielding errors are at-bats, not hits.

### `singles`

```text
SUM(analytics.player_game_batting.singles)
```

### `doubles`

```text
SUM(analytics.player_game_batting.doubles)
```

### `triples`

```text
SUM(analytics.player_game_batting.triples)
```

### `home_runs`

```text
SUM(analytics.player_game_batting.home_runs)
```

### `walks`

```text
SUM(analytics.player_game_batting.walks)
```

The source counts both `walk` and `intent_walk` as walks.

### `hit_by_pitch`

```text
SUM(analytics.player_game_batting.hit_by_pitch)
```

### `strikeouts`

```text
SUM(analytics.player_game_batting.strikeouts)
```

The source counts both `strikeout` and `strikeout_double_play` as strikeouts.

### `sac_flies`

The source column is `sacrifice_flies`. The season table uses the same physical name so the rollup stays one-to-one.

```text
SUM(analytics.player_game_batting.sacrifice_flies)
```

The source increment is the `sac_fly` plate-appearance outcome.

### `sac_bunts`

The source column is `sacrifice_bunts`. The season table uses the same physical name.

```text
SUM(analytics.player_game_batting.sacrifice_bunts)
```

The source increment is the `sac_bunt` plate-appearance outcome.

`runs` and `rbi` are not present on `analytics.player_game_batting` or `curated.plate_appearance` and are not defined here.

---

# Derived Rate Metrics

Unlike `analytics.player_game_batting`, this table materializes the common rate statistics. Season batting is the surface that later average, OBP, slugging, and OPS analysis will query.

Rates are calculated from the season totals, not by averaging game-level rates.

A denominator of zero produces `NULL`, not `0`.

---

## `batting_average`

```text
batting_average = hits / at_bats
```

`NULL` when `at_bats = 0`.

---

## `on_base_percentage`

```text
on_base_percentage =
    (hits + walks + hit_by_pitch)
    / (at_bats + walks + hit_by_pitch + sac_flies)
```

`sac_flies` is the inherited `sacrifice_flies` total.

`NULL` when the denominator is `0`.

Sacrifice bunts are not part of the official OBP denominator. Catcher interference, truncated plate appearances, and NULL-outcome plate appearances also stay out of the denominator. They already affect `plate_appearances` at the game level.

Intentional walks are already included in `walks`.

---

## `slugging_percentage`

First calculate total bases:

```text
total_bases =
    singles
  + (2 * doubles)
  + (3 * triples)
  + (4 * home_runs)
```

Then:

```text
slugging_percentage = total_bases / at_bats
```

`NULL` when `at_bats = 0`.

`total_bases` is an intermediate value only. It is not persisted. The addends needed to recompute it are already stored, and the first version has no separate total-bases product.

---

## `ops`

```text
ops = on_base_percentage + slugging_percentage
```

`NULL` unless both OBP and SLG are non-NULL.

A player with walks but no at-bats can have an on-base percentage and still have `NULL` slugging and `NULL` OPS.

---

## `strikeout_rate`

```text
strikeout_rate = strikeouts / plate_appearances
```

`NULL` when `plate_appearances = 0`.

This is a plate-appearance rate, not an at-bat rate.

---

## `walk_rate`

```text
walk_rate = walks / plate_appearances
```

`NULL` when `plate_appearances = 0`.

---

# Initial Analytics Schema

### Dimensions

```text
player_id
season_id
```

### Counting Measures

```text
games
plate_appearances
at_bats
hits
singles
doubles
triples
home_runs
walks
hit_by_pitch
strikeouts
sacrifice_flies
sacrifice_bunts
```

`sacrifice_flies` and `sacrifice_bunts` are the included `sac_flies` and `sac_bunts` metrics.

### Derived Measures

```text
batting_average
on_base_percentage
slugging_percentage
ops
strikeout_rate
walk_rate
```

### Database Defaults

```text
created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
```

`created_at` is populated by the database on insert and is not supplied by the loader. On refresh, it is left unchanged.

---

# Physical Design

The business key and primary key are:

```text
(player_id, season_id)
```

A composite primary key is preferred over a surrogate identity key because this table is derived state at a stable grain, matching `analytics.player_pitch_type_effectiveness`.

Foreign keys:

```text
player_id → curated.player.player_id
season_id → curated.season.season_id
```

No additional indexes are required for the first version.

Counting columns are `INTEGER NOT NULL` with `>= 0` checks.

Rate columns are nullable numerics. Recommended storage:

```text
batting_average      NUMERIC(7,6)   NULL or 0 to 1
on_base_percentage   NUMERIC(7,6)   NULL or 0 to 1
strikeout_rate       NUMERIC(7,6)   NULL or 0 to 1
walk_rate            NUMERIC(7,6)   NULL or 0 to 1
slugging_percentage  NUMERIC(8,6)   NULL or 0 to 4
ops                  NUMERIC(8,6)   NULL or 0 to 5
```

Slugging and OPS are not bounded by 1. A four-home-run game produces a slugging percentage of 4.000. OPS can therefore exceed 2.000.

Python `float | None` values may be persisted directly. The first version will not introduce custom rounding beyond PostgreSQL `NUMERIC` scale.

---

# Load Behavior

The loader extracts game-level batting rows, attaches `season_id`, aggregates to `(player_id, season_id)`, and persists the result.

The caller owns the transaction.

This table is derived state. It must be safely rebuildable from `analytics.player_game_batting`. Reruns must refresh existing rows rather than accumulate counts or fail on the primary key.

The loader will use PostgreSQL upsert:

```text
INSERT ...
ON CONFLICT (player_id, season_id)
DO UPDATE
```

Conflict updates replace counting and rate columns with the current derived payload. `created_at` is not updated.

This is an intentional adaptation from `analytics.player_game_batting` and `analytics.player_game_pitching`, which insert once at a historical game grain and treat duplicates as integrity errors.

Empty source input must not fail and must not insert rows.

---

# Metrics Explicitly Deferred

The following traditional counting statistics are deferred:

```text
runs
rbi
```

They cannot be sourced from `analytics.player_game_batting`. That table has no run or RBI columns.

They also cannot be sourced from the current curated plate-appearance model. `curated.plate_appearance` records outcome, inning, and participants; it does not record runs scored or runs batted in.

The first version will not:

* infer runs from home runs
* infer RBI from hits or sacrifice flies
* query raw Statcast score fields to approximate them
* add `runs` or `rbi` columns populated with zeros

Those approximations would present incomplete baseball facts as if they were authoritative.

When run and RBI support is added, it should be designed first at a curated or game-level batting source, then rolled into this season table.

The following metrics and products are also deferred:

```text
wOBA
wRC+
BABIP
ISO
total_bases
extra_base_hits
grounded_into_double_play
caught_stealing
stolen_bases
rolling averages
league-adjusted metrics
park-adjusted metrics
platoon splits
team-context metrics
team splits
game-type splits
```

They can be later ADRs or derived query surfaces.

---

# Null and Division Handling

Rate metrics must use safe division.

Examples:

```text
at_bats = 0
hits = 0
batting_average = NULL
slugging_percentage = NULL
```

```text
at_bats = 0
walks = 1
hit_by_pitch = 0
sacrifice_flies = 0
on_base_percentage = 1.000
slugging_percentage = NULL
ops = NULL
```

```text
plate_appearances = 0
strikeout_rate = NULL
walk_rate = NULL
```

A produced row from the current game-level batting source will have `plate_appearances >= 1`, so strikeout and walk rates should be defined in practice. The `NULL` rule still applies.

---

# Data Integrity Expectations

The following rules are guaranteed by the current `player_game_batting` increment model, and therefore remain true after summation:

```text
(player_id, season_id) is unique
all count metrics >= 0
hits = singles + doubles + triples + home_runs
at_bats <= plate_appearances
hits <= at_bats
home_runs <= hits
walks <= plate_appearances
hit_by_pitch <= plate_appearances
strikeouts <= plate_appearances
sacrifice_flies <= plate_appearances
sacrifice_bunts <= plate_appearances
```

`hits = singles + doubles + triples + home_runs` is guaranteed because the source increment objects set `hits` only together with exactly one of those four hit types.

`games` is not a source column. For any produced season row it is still true that:

```text
games >= 1
games <= plate_appearances
```

because every `player_game_batting` row is created from at least one plate appearance, and `games` counts distinct `game_id` values from those rows.

The following rate bounds are guaranteed when the rate is not NULL:

```text
0 <= batting_average <= 1
0 <= on_base_percentage <= 1
0 <= strikeout_rate <= 1
0 <= walk_rate <= 1
```

The following are not `[0, 1]` rates and must not be constrained that way:

```text
0 <= slugging_percentage <= 4        when not NULL
0 <= ops <= 5                        when not NULL
ops = on_base_percentage + slugging_percentage
    when both components are not NULL
```

Cross-checks against the source table, after joining source rows to `curated.game` for the same population:

```text
SUM(player_season_batting.plate_appearances)
  = SUM(player_game_batting.plate_appearances)

SUM(player_season_batting.at_bats)
  = SUM(player_game_batting.at_bats)

SUM(player_season_batting.hits)
  = SUM(player_game_batting.hits)

COUNT(*)
  = COUNT(DISTINCT (player_id, season_id))
    from player_game_batting joined to curated.game
```

The same equality should hold for singles, doubles, triples, home runs, walks, hit by pitch, strikeouts, sacrifice flies, and sacrifice bunts.

`SUM(games)` will generally be less than the number of `player_game_batting` rows because one game can produce multiple team-grain rows and because `games` is distinct by game, not by source row.

---

# Rationale

Season batting is a rollup of an existing analytics table, not a new reading of raw or curated events.

That choice keeps batting outcome rules in one place:

```text
curated.plate_appearance
 ↓
analytics.player_game_batting
 ↓
analytics.player_season_batting
```

Materializing rates at season grain is useful because that is the common reporting grain. Leaving rates unmaterialized on `player_game_batting` remains correct; game lines are counting-stat facts, and season lines are the first batting average / OBP / slugging / OPS product.

Using `curated.game.season_id` avoids storing season redundantly on the game-level batting table.

Using `COUNT(DISTINCT game_id)` keeps the `games` statistic honest when the source grain includes `team_id`.

Deferring `runs` and `rbi` preserves the project's rule that analytics metrics must have an explicit authoritative source.

---

# Alternatives Considered

### Re-derive season batting from `curated.plate_appearance`

This would ignore the completed game-level batting table and duplicate its outcome matrix.

Rejected because the season table would drift if game-level rules later change.

### Store `season_id` on `analytics.player_game_batting`

This would make season extraction a simple group-by without a join.

Rejected because `curated.game.season_id` already provides the relationship. Copying it would denormalize a curated fact into an analytics table that does not otherwise need it.

### Include `team_id` in the grain

This would produce player-season-team batting lines.

Rejected for the first version. Traditional season batting is player/season. Team splits can be a later table.

### Materialize `runs` and `rbi` immediately

This would match a conventional baseball line score.

Rejected until an authoritative curated or game-level source exists. Inventing those values from hits or raw score fields would violate the analytics source rule.

### Leave rates unmaterialized

This would match `player_game_batting`.

Rejected because the purpose of this table is season-level average, OBP, slugging, OPS, and rate analysis.

### Persist `total_bases`

This would make slugging easier to inspect.

Rejected because singles, doubles, triples, and home runs already determine total bases, and the first version has no separate total-bases product.

---

# Consequences

### Positive

* Establishes a clean player/season batting grain.
* Reuses existing game-level batting facts instead of duplicating outcome rules.
* Uses the existing game-to-season relationship.
* Documents official rate formulas before implementation.
* Distinguishes undefined rates from zero rates.
* Creates a foundation for later batting-average, OBP, slugging, and OPS features.

### Trade-offs

* `runs` and `rbi` are absent from the first season line.
* Multi-team seasons are collapsed into one row.
* Game-type splits are not available.
* Slugging and OPS need a wider numeric range than the `[0, 1]` rate columns used by pitch-type effectiveness.

---

# Future Extensions

Potential later counting statistics:

```text
runs
rbi
total_bases
extra_base_hits
grounded_into_double_play
```

Potential later rate statistics:

```text
ISO
BABIP
wOBA
wRC+
```

Potential later grains:

```text
(player_id, season_id, team_id)
(player_id, season_id, game_type_id)
```

Potential later products:

```text
rolling batting lines
year-over-year batting trends
league and team batting comparison
league-adjusted metrics
park-adjusted metrics
platoon splits
```

These should be separate analytical requirements.

---

# Implementation Sequence

Following this decision, implementation should proceed in this order:

1. Create the Alembic migration for `analytics.player_season_batting`.
2. Implement extraction from `analytics.player_game_batting` joined to `curated.game`.
3. Implement transformation, including distinct-game counting and rate formulas.
4. Add unit tests for aggregation, distinct games, rate formulas, and zero denominators.
5. Implement the analytics loader with upsert semantics.
6. Create a rollback-only validation script.
7. Perform the initial permanent load.
8. Run database-level validation against `analytics.player_game_batting`.
9. Commit and merge the completed feature.

Do not implement this table by reading raw Statcast or by re-aggregating `curated.plate_appearance`.

---

## Decision Summary

The platform will model season batting at:

```text
(player_id, season_id)
```

using `analytics.player_game_batting` as the authoritative counting-stat source and `curated.game.season_id` for season identity.

The first version will store summed counting statistics plus:

```text
games
batting_average
on_base_percentage
slugging_percentage
ops
strikeout_rate
walk_rate
```

`runs` and `rbi` are deferred until they have an authoritative source. Advanced metrics such as wOBA, wRC+, BABIP, ISO, rolling averages, league-adjusted metrics, park-adjusted metrics, platoon splits, and team-context metrics are also deferred.
