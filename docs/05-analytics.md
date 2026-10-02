# Analytics Layer

## 1. Player Game Batting

### 1.1 Purpose

The first analytics model provides a convenient batting-statistical surface derived from authoritative curated data.

The analytics layer does not replace or duplicate the authoritative facts in the curated layer. It transforms curated facts into analytical grains that are convenient for reporting, analysis, and downstream application features.

### 1.2 Analytical Grain

The initial analytical model is:

> **One row per player, per game, per team.**

The proposed table is:

```text
analytics.player_game_batting
```

The business grain is:

```text
(player_id, game_id, team_id)
```

This combination must be unique.

The `team_id` is included because a player can potentially have multiple team assignments within the same game.

### 1.3 Source Data

The player-game batting model is derived primarily from:

```text
curated.plate_appearance
curated.game_player
curated.game
curated.outcome_type
```

`curated.pitch` may be used for future analytical measures that require pitch-level information, but the initial batting counting statistics are derived from plate-appearance outcomes.

The curated layer remains authoritative. The analytics layer contains derived measurements and does not become a second source of truth for the underlying baseball events.

---

## 2. Initial Batting Measures

The initial model contains the following counting statistics:

```text
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

Derived rate statistics such as:

```text
batting_average
on_base_percentage
slugging_percentage
ops
```

are not initially materialized in the physical table.

They can be calculated from the counting statistics.

---

## 3. Plate Appearance Derivation Rules

Every curated plate appearance contributes to the `plate_appearances` count for its player/game/team grain, including records whose `outcome_type_id` is NULL.

The outcome determines which additional batting statistics are incremented.

### 3.1 Outcome Derivation Matrix

| Outcome                     | PA | AB |  H | 1B | 2B | 3B | HR | BB | HBP |  K | SF | SH |
| --------------------------- | -: | -: | -: | -: | -: | -: | -: | -: | --: | -: | -: | -: |
| `single`                    |  1 |  1 |  1 |  1 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `double`                    |  1 |  1 |  1 |  0 |  1 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `triple`                    |  1 |  1 |  1 |  0 |  0 |  1 |  0 |  0 |   0 |  0 |  0 |  0 |
| `home_run`                  |  1 |  1 |  1 |  0 |  0 |  0 |  1 |  0 |   0 |  0 |  0 |  0 |
| `walk`                      |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  1 |   0 |  0 |  0 |  0 |
| `intent_walk`               |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  1 |   0 |  0 |  0 |  0 |
| `hit_by_pitch`              |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   1 |  0 |  0 |  0 |
| `strikeout`                 |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  1 |  0 |  0 |
| `strikeout_double_play`     |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  1 |  0 |  0 |
| `sac_fly`                   |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  1 |  0 |
| `sac_bunt`                  |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  1 |
| `field_out`                 |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `field_error`               |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `force_out`                 |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `grounded_into_double_play` |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `double_play`               |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `fielders_choice`           |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `fielders_choice_out`       |  1 |  1 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `catcher_interf`            |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `truncated_pa`              |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |
| `NULL` outcome              |  1 |  0 |  0 |  0 |  0 |  0 |  0 |  0 |   0 |  0 |  0 |  0 |

### 3.2 Special Outcome Rules

#### Strikeout Double Play

`strikeout_double_play` counts as:

```text
plate_appearances += 1
at_bats += 1
strikeouts += 1
```

It does not count as a hit.

#### Fielding Error

A `field_error` counts as an at-bat but not a hit:

```text
plate_appearances += 1
at_bats += 1
```

#### Catcher Interference

`catcher_interf` contributes a plate appearance but does not count as an at-bat.

#### Truncated Plate Appearance

`truncated_pa` contributes a plate appearance but does not count as an at-bat or any other batting statistic.

#### NULL Outcome

A plate appearance with `outcome_type_id IS NULL` is retained in the analytical population as one plate appearance.

Because there is no authoritative outcome from which to derive a batting event, it does not increment any other batting statistic.

The transformation must not infer a batting outcome from unrelated fields.

---

## 4. Initial Analytical Invariants

The analytics transformation should enforce or test the following relationships.

### Hits

```text
hits = singles + doubles + triples + home_runs
```

### Plate appearances

```text
plate_appearances >= at_bats
```

### At-bats

At-bats consist only of qualifying batting outcomes and exclude:

```text
walk
intent_walk
hit_by_pitch
sac_fly
sac_bunt
catcher_interf
truncated_pa
NULL outcome
```

### Batting average

When calculated:

```text
batting_average = hits / at_bats
```

when `at_bats > 0`.

### Slugging percentage

When calculated:

```text
slugging_percentage =
    (singles + 2*doubles + 3*triples + 4*home_runs)
    / at_bats
```

when `at_bats > 0`.

### On-base percentage

The exact formula used by the application should be documented before implementation because different baseball contexts can use slightly different definitions.

---

## 5. Design Principle

The analytics layer is a derived analytical representation.

The authoritative event-level data remains in the curated layer:

```text
raw
 ↓
curated
 ↓
analytics
```

Analytics transformations should be deterministic, documented, and testable.

Changes to the analytical model must not modify the meaning of authoritative curated facts.
