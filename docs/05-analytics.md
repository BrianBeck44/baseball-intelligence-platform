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

T### Validation Conclusion

The current curated data validates the proposed `analytics.player_game_batting` design.

Specifically:

1. The player/game/team grain produces **672** unique analytics rows from **2,500** plate appearances.
2. All source player, game, and team relationships resolve successfully.
3. Every player/game/team combination maps to a valid `curated.game_team` record.
4. The batting counting-stat derivation produces internally consistent totals.
5. Special and incomplete outcomes are handled explicitly rather than inferred.
6. The analytics model has been implemented and validated against the current curated dataset.

The player-game batting model is now an established foundational analytics model for downstream player performance analysis.

The next analytical capability is **Player Performance Trends**, as defined in Section 3.


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

## 3. Player Performance Trends

### 3.1 Purpose

The next analytical capability is to evaluate how an individual player's performance changes over time.

The initial use case is:

> **How has a player's offensive performance changed over time?**

This model builds on the foundational game-level analytics already provided by:

```text
analytics.player_game_batting
analytics.player_game_pitching
```

The initial implementation will focus on batting performance.

The purpose is to support analytical questions such as:

* Is a player's recent performance improving or declining?
* How does recent performance compare with the player's season-to-date performance?
* Has a player's strikeout or walk rate changed over a recent period?
* Has a player's power production changed over time?
* Is a player's recent performance materially different from their established baseline?

This analysis is intended to provide the foundation for future performance-change analysis, including eventual before-and-after analysis around significant events such as injuries.

### 3.2 Source Data

The initial batting trend analysis will be derived from:

```text
analytics.player_game_batting
curated.game
curated.season
```

`analytics.player_game_batting` provides the authoritative analytical counting statistics for each player/game/team grain.

`curated.game` provides the game date required to establish the chronological ordering of player performance.

The curated layer remains authoritative for the underlying baseball events.

The trend analysis does not create a new source of truth. It derives temporal measurements from the existing analytical and curated layers.

### 3.3 Initial Analytical Grain

The fundamental source grain remains:

```text
(player_id, game_id, team_id)
```

from:

```text
analytics.player_game_batting
```

Trend calculations will order a player's game-level observations chronologically by game date.

A player may have multiple team records within a game. Therefore, the existing player/game/team grain must not be collapsed without an explicit analytical rule.

For player-level trend calculations, statistics from all applicable team records for the same player and game date may be aggregated when the analytical question requires a player-level result.

The implementation must preserve the distinction between:

```text
player + game + team
```

and:

```text
player + date
```

rather than assuming they are interchangeable.

### 3.4 Initial Trend Windows

The initial trend analysis will support the following conceptual windows:

```text
game-to-game
7-game rolling
14-game rolling
30-game rolling
season-to-date
```

These windows are intended to answer different analytical questions.

#### Game-to-Game

Provides the player's individual game performance and allows performance to be plotted or compared sequentially over time.

#### 7-Game Rolling

Provides a short-term performance indicator that can identify recent changes while remaining responsive to current performance.

#### 14-Game Rolling

Provides a medium-term performance indicator that reduces some of the volatility of individual games while still identifying relatively recent changes.

#### 30-Game Rolling

Provides a longer-term recent-performance indicator that can be compared with shorter windows and season-level performance.

#### Season-to-Date

Provides the player's cumulative performance from the beginning of the season through the current game.

The exact number of games included in a rolling window is based on games in which the player has a qualifying batting record, not calendar days.

### 3.5 Initial Counting Metrics

The trend analysis will use the existing batting counting statistics:

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

Additional metrics should not be introduced into the trend model unless their derivation rules are documented and validated.

### 3.6 Derived Rate Metrics

Rate statistics will be calculated from aggregated counting statistics rather than by averaging individual game-level rates.

The following derived metrics are initially supported:

```text
batting_average
on_base_percentage
slugging_percentage
ops
strikeout_rate
walk_rate
```

#### Batting Average

For a given analytical window:

```text
batting_average =
    SUM(hits) / SUM(at_bats)
```

when the aggregated at-bats are greater than zero.

#### Slugging Percentage

For a given analytical window:

```text
slugging_percentage =
    (
        SUM(singles)
        + 2 * SUM(doubles)
        + 3 * SUM(triples)
        + 4 * SUM(home_runs)
    )
    / SUM(at_bats)
```

when the aggregated at-bats are greater than zero.

#### On-Base Percentage

The exact on-base percentage formula must use the application's documented baseball definition.

The implementation must calculate OBP from aggregated numerator and denominator components rather than averaging game-level OBP values.

The selected OBP definition must be explicitly documented before implementation.

#### OPS

OPS is calculated as:

```text
ops =
    on_base_percentage + slugging_percentage
```

when both component rates are defined.

#### Strikeout Rate

For a given analytical window:

```text
strikeout_rate =
    SUM(strikeouts) / SUM(plate_appearances)
```

when the aggregated plate appearances are greater than zero.

#### Walk Rate

For a given analytical window:

```text
walk_rate =
    SUM(walks) / SUM(plate_appearances)
```

when the aggregated plate appearances are greater than zero.

### 3.7 Rate Calculation Principle

The trend model must not calculate rolling rates by averaging individual game-level rates.

For example, this approach is incorrect:

```text
AVG(game_ops)
```

for a rolling OPS.

Instead, the underlying counting statistics must first be aggregated across the analytical window and the rate must then be calculated.

For example:

```text
rolling_hits
rolling_at_bats
```

are calculated first, followed by:

```text
rolling_batting_average =
    rolling_hits / rolling_at_bats
```

This ensures that games with different numbers of plate appearances are weighted correctly.

The same principle applies to OBP, SLG, OPS, strikeout rate, and walk rate.

### 3.8 Minimum Sample Considerations

Small samples can produce highly volatile rates.

For example:

```text
1 AB
1 H
```

produces:

```text
AVG = 1.000
```

but does not represent a meaningful performance trend.

Therefore, rate-based trend analysis should support minimum sample thresholds.

The initial implementation should retain the underlying counting statistics even when a rate is not considered statistically useful.

Minimum sample thresholds should be defined separately for individual analytical use cases rather than hard-coded into the foundational game-level model.

The initial trend implementation should document any threshold used for:

```text
7-game
14-game
30-game
season-to-date
```

rate calculations.

### 3.9 Baseline Comparison

A future extension of the trend analysis will compare recent performance against a player's established baseline.

The conceptual model is:

```text
recent performance
        ↓
baseline performance
        ↓
difference
```

For example:

```text
30-game OPS       = .925
season-to-date OPS = .780
difference         = +.145
```

Baseline comparisons should be calculated from aggregated counting statistics whenever possible.

The initial implementation should avoid declaring a player to be "improving" or "declining" solely from a single rate difference. Such classifications may be added later when sufficient sample-size and statistical rules have been defined.

### 3.10 Team Changes

A player can change teams during a season.

The underlying game-level model retains:

```text
team_id
```

to preserve the authoritative player/game/team relationship.

Player-level trend analysis may aggregate across teams when answering questions about the player's overall performance.

Team-specific analysis must retain the team dimension.

The implementation must therefore distinguish between:

```text
player overall trend
```

and:

```text
player/team trend
```

rather than silently combining the two.

### 3.11 No New Physical Table Initially

The first implementation of player performance trends should not automatically introduce a new persisted analytics table.

The initial approach should evaluate whether PostgreSQL views and window functions can provide the required trend calculations directly from:

```text
analytics.player_game_batting
curated.game
```

A physical trend table should only be introduced if there is a demonstrated performance, reuse, or application-serving requirement that justifies materializing the results.

This follows the project's general principle of avoiding unnecessary duplication of derived data.

### 3.12 Future Pitching Trends

The same temporal framework can later be applied to:

```text
analytics.player_game_pitching
```

to support questions such as:

* Is a pitcher's strikeout rate changing?
* Is walk rate increasing?
* Is the number of pitches per batter changing?
* Is recent opponent production different from the season baseline?
* How has a pitcher's recent workload changed?

Pitching trend analysis should be implemented as a separate analytical model once the batting trend methodology has been validated.

### 3.13 Future Event-Based Analysis

Player performance trends are intended to provide the foundation for future event-based analysis.

A future model may incorporate authoritative events such as injuries and compare performance across defined periods:

```text
event
   ↓
pre-event performance
   ↓
event
   ↓
post-event performance
```

For example:

```text
30 games before event
        vs.
30 games after event
```

Such analysis will require an authoritative event source and explicitly defined event dates.

Injury analysis is therefore outside the initial scope of the player performance trend model.

### 3.14 Initial Validation Requirements

The trend implementation should validate:

* chronological ordering by game date
* correct player/game/team relationships
* correct rolling-window boundaries
* correct season boundaries
* correct handling of players changing teams
* correct aggregation of counting statistics
* correct rate calculations from aggregated counts
* no averaging of individual game-level rates
* correct handling of zero denominators
* correct handling of NULL or incomplete batting outcomes inherited from `player_game_batting`
* consistency between season-to-date totals and the underlying game-level data

For any given player and analytical window:

```text
rolling_hits =
    SUM(game_hits)
```

and equivalent relationships should hold for all other counting statistics.

Derived rates must reconcile to the corresponding aggregated counting statistics.

### 3.15 Initial Scope

The initial player performance trend model includes:

```text
game-to-game performance
7-game rolling performance
14-game rolling performance
30-game rolling performance
season-to-date performance
batting counting statistics
batting average
on-base percentage
slugging percentage
OPS
strikeout rate
walk rate
```

The initial model intentionally excludes:

```text
injury events
injury attribution
statistical significance testing
predictive modeling
player projections
league-adjusted metrics
park-adjusted metrics
pitch-level trend analysis
automated "hot/cold" classifications
```

These may be introduced as separate analytical capabilities after the foundational trend calculations have been validated.

### 3.16 Design Principle

Player performance trends are a derived analytical layer built on top of the existing game-level analytical models.

The intended architecture is:

```text
raw
  ↓
curated
  ↓
analytics.player_game_batting
  ↓
player performance trends
```

The trend layer should favor reusable analytical calculations over duplicated persisted data.

The initial implementation should therefore establish the analytical definitions, validate the calculations, and determine whether PostgreSQL views and window functions are sufficient before introducing another physical analytics table.
