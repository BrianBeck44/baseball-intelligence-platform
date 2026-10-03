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

## Analytics Design Validation

### Player-Game-Team Grain Validation

The proposed grain for `analytics.player_game_batting` is:

> One row per player, per game, per team.

The current curated dataset was validated against this grain using `curated.plate_appearance`.

Validation results:

* Total plate appearances: **2,500**
* Distinct `(player_id, game_id, batter_team_id)` combinations: **672**
* Unresolved player, game, or team references: **0**
* Invalid `(game_id, team_id)` combinations against `curated.game_team`: **0**

This confirms that the curated plate appearance data can be deterministically aggregated into one analytics row for each `(player_id, game_id, team_id)` combination.

The analytics table will therefore enforce the business key:

```text
(player_id, game_id, team_id)
```

with a unique constraint.

The relationship between `game_id` and `team_id` will also be enforced through a composite foreign key to:

```text
curated.game_team(game_id, team_id)
```

### Batting Statistic Derivation Validation

The batting counting-stat derivation was independently validated against the current curated plate appearance data.

The resulting totals are:

| Measure           | Total |
| ----------------- | ----: |
| Plate appearances | 2,500 |
| At bats           | 2,203 |
| Hits              |   489 |
| Singles           |   325 |
| Doubles           |    98 |
| Triples           |     5 |
| Home runs         |    61 |
| Walks             |   222 |
| Hit by pitch      |    40 |
| Strikeouts        |   585 |
| Sacrifice flies   |    19 |
| Sacrifice bunts   |     8 |

The component relationships also reconcile:

```text
Hits = Singles + Doubles + Triples + Home Runs
489 = 325 + 98 + 5 + 61
```

```text
Walks = Walk + Intent Walk
222 = 216 + 6
```

```text
Strikeouts = Strikeout + Strikeout Double Play
585 = 584 + 1
```

These results confirm that the proposed derivation rules produce internally consistent batting totals from the curated plate appearance data.

### Special Outcome Handling

The following outcomes were explicitly validated:

| Outcome          | PA | AB | Hits |
| ---------------- | -: | -: | ---: |
| `catcher_interf` |  1 |  0 |    0 |
| `truncated_pa`   |  6 |  0 |    0 |
| NULL outcome     |  1 |  0 |    0 |

A plate appearance with a NULL `outcome_type_id` is still counted as a plate appearance because the plate appearance itself is authoritative. However, it contributes to none of the other batting counting statistics because no authoritative outcome is available.

Similarly, `catcher_interf` and `truncated_pa` count as plate appearances but do not contribute to at-bats, hits, walks, hit by pitch, strikeouts, sacrifice flies, or sacrifice bunts under the current analytics rules.

The implementation will not infer a batting result from unrelated pitch-level or source fields when the authoritative plate appearance outcome is unavailable.

### Validation Conclusion

The current curated data validates the proposed `analytics.player_game_batting` design.

Specifically:

1. The player/game/team grain produces **672** unique analytics rows from **2,500** plate appearances.
2. All source player, game, and team relationships resolve successfully.
3. Every player/game/team combination maps to a valid `curated.game_team` record.
4. The batting counting-stat derivation produces internally consistent totals.
5. Special and incomplete outcomes are handled explicitly rather than inferred.
6. The analytics model can therefore be implemented as a physical table without introducing additional source-level assumptions.

The next implementation step is to create the Alembic migration for `analytics.player_game_batting`.

## Player Game Pitching

### Purpose and Grain

The `analytics.player_game_pitching` table provides game-level pitching performance
aggregated from the curated plate appearance and pitch data.

The grain is one row per pitcher, per game, per pitching team.

Business key:

```text
(pitcher_id, game_id, team_id)
```

The table provides a stable game-level pitching summary while preserving the
detailed pitch-level data in `curated.pitch` for future pitch analysis.

### Source Data

The primary sources are:

* `curated.plate_appearance`
* `curated.pitch`

`curated.plate_appearance` is authoritative for pitcher, pitching team, game,
and plate-appearance outcomes.

`curated.pitch` is authoritative for individual pitch observations and is used
to calculate total pitches.

The pitching team is taken directly from
`curated.plate_appearance.pitcher_team_id`; it is not inferred from other
game data.

### Initial Measures

The initial analytics table contains the following measures:

| Measure             | Definition                                       |
| ------------------- | ------------------------------------------------ |
| `batters_faced`     | Number of plate appearances faced by the pitcher |
| `pitches`           | Number of pitches thrown by the pitcher          |
| `hits_allowed`      | Singles + doubles + triples + home runs          |
| `home_runs_allowed` | Home runs allowed                                |
| `walks`             | Walks + intentional walks                        |
| `hit_by_pitch`      | Hit by pitch                                     |
| `strikeouts`        | Strikeouts + strikeout double plays              |

Rate statistics such as ERA, WHIP, K/9, BB/9, HR/9, opponent batting average,
and opponent slugging percentage are intentionally deferred. They can be
derived from the foundational measures without storing redundant values.

### Plate Appearance Outcome Derivation

Each plate appearance faced by a pitcher contributes one to `batters_faced`.

The following outcome mappings are used:

| Outcome                 | BF |  H | HR | BB | HBP |  K |
| ----------------------- | -: | -: | -: | -: | --: | -: |
| `single`                |  1 |  1 |  0 |  0 |   0 |  0 |
| `double`                |  1 |  1 |  0 |  0 |   0 |  0 |
| `triple`                |  1 |  1 |  0 |  0 |   0 |  0 |
| `home_run`              |  1 |  1 |  1 |  0 |   0 |  0 |
| `walk`                  |  1 |  0 |  0 |  1 |   0 |  0 |
| `intent_walk`           |  1 |  0 |  0 |  1 |   0 |  0 |
| `hit_by_pitch`          |  1 |  0 |  0 |  0 |   1 |  0 |
| `strikeout`             |  1 |  0 |  0 |  0 |   0 |  1 |
| `strikeout_double_play` |  1 |  0 |  0 |  0 |   0 |  1 |
| All other outcomes      |  1 |  0 |  0 |  0 |   0 |  0 |

A NULL outcome is also treated as a plate appearance faced with no derived
result.

This derivation intentionally uses the authoritative outcome recorded on the
plate appearance rather than attempting to reconstruct the result from
individual pitch events.

### Pitch Count Derivation

`pitches` is calculated from rows in `curated.pitch` associated with the
pitcher's plate appearances.

Each row in `curated.pitch` represents an individual pitch observation.
Therefore, the pitch count is the number of associated pitch rows.

The pitch-level outcome is retained in `curated.pitch` and is not collapsed
into the game-level pitching aggregate.

The current curated pitch outcome vocabulary includes:

* `ball`
* `foul`
* `hit_into_play`
* `called_strike`
* `swinging_strike`
* `blocked_ball`
* `swinging_strike_blocked`
* `foul_tip`
* `hit_by_pitch`
* `automatic_ball`
* `foul_bunt`
* `missed_bunt`

No attempt is made in this initial model to derive aggregate `strikes` or
`balls` from the `curated.pitch.balls` and `curated.pitch.strikes` columns.

Those columns represent the count state associated with a pitch rather than
a simple classification of the individual pitch as a ball or strike.
Pitch-level outcome analysis can instead use `curated.pitch_outcome_type`.

### Pitch-Level Analysis Preservation

`analytics.player_game_pitching` is a game-level analytical projection and
is not intended to replace the detailed pitch data.

The architecture intentionally preserves:

```text
raw
  ↓
curated.pitch
  ↓
analytics.player_game_pitching
```

The curated layer remains the authoritative source for individual pitches and
their characteristics.

This preserves the ability to perform future pitch-level analysis including:

* pitch-type effectiveness
* pitch velocity
* spin rate
* pitch movement
* pitch location
* whiff rate
* called-strike rate
* contact rate
* batting outcomes by pitch type
* pitch effectiveness by count
* pitch effectiveness by batter or pitcher

For example, curveball effectiveness can be analyzed directly from
`curated.pitch` using the associated pitch type and pitch-level outcome data.
That analysis does not depend on the game-level pitching aggregate retaining
individual pitch characteristics.

### Relationship Integrity

The table uses the following relationships:

```text
pitcher_id → curated.player.player_id
game_id    → curated.game.game_id
team_id    → curated.team.team_id
```

The combination:

```text
(game_id, team_id)
```

must also resolve to:

```text
curated.game_team(game_id, team_id)
```

This ensures that the pitching team actually participated in the game.

The pitching team is sourced directly from
`curated.plate_appearance.pitcher_team_id`.

### Validation Invariants

The following invariants should hold:

* `batters_faced` is non-negative.
* `pitches` is non-negative.
* `hits_allowed` is non-negative.
* `home_runs_allowed` is non-negative.
* `walks` is non-negative.
* `hit_by_pitch` is non-negative.
* `strikeouts` is non-negative.
* `home_runs_allowed <= hits_allowed`.
* `hits_allowed <= batters_faced`.
* `walks <= batters_faced`.
* `hit_by_pitch <= batters_faced`.
* `strikeouts <= batters_faced`.
* `pitches >= batters_faced` for the current curated dataset.
* `(pitcher_id, game_id, team_id)` is unique.
* Every pitcher resolves to `curated.player`.
* Every game resolves to `curated.game`.
* Every team resolves to `curated.team`.
* Every `(game_id, team_id)` resolves to `curated.game_team`.

The aggregate `hits_allowed` value must equal the sum of singles, doubles,
triples, and home runs derived from the underlying plate appearances.

### Design Principles

The analytics layer follows the project's general principle of deriving
analytical projections from authoritative curated facts.

For player-game pitching:

```text
raw Statcast data
       ↓
curated.plate_appearance
curated.pitch
       ↓
analytics.player_game_pitching
```

The curated layer preserves detailed authoritative baseball facts.

The analytics layer provides a convenient game-level representation for
common pitching analysis.

Derived rates and specialized analytical models should be created from these
foundational measures rather than duplicating authoritative facts unnecessarily.

### Initial Scope

The first version intentionally excludes:

* innings pitched
* outs recorded
* earned runs
* runs allowed
* ERA
* WHIP
* K/9
* BB/9
* HR/9
* opponent batting average
* opponent slugging percentage
* aggregate pitch-level strike totals
* aggregate pitch-level ball totals
* pitch-type effectiveness metrics

These measures can be added as separate analytical models or derived metrics
when the underlying curated data and derivation rules provide authoritative
support.

The detailed pitch data remains available in `curated.pitch` for future
pitch-level analytics without requiring changes to the foundational
`player_game_pitching` grain.
