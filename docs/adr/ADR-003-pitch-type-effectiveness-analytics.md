# ADR-003: Pitch Type Effectiveness Analytics

**Status:** Accepted
**Date:** 2026-10-03
**Decision Type:** Analytics / Data Modeling

## Context

The Baseball Intelligence Platform currently contains curated pitch-level and plate-appearance data and analytics tables for player-game batting and player-game pitching.

The next analytics capability will measure how individual pitch types perform for each pitcher.

The goal is to move beyond traditional game-level aggregation and demonstrate pitch-level baseball intelligence using the curated data layer.

The initial analytics table will be:

```text
analytics.player_pitch_type_effectiveness
```

The table will aggregate pitch-level behavior across the currently loaded dataset.

---

## Decision

Create `analytics.player_pitch_type_effectiveness` at the following analytical grain:

```text
(player_id, pitch_type_id)
```

Each row represents the aggregate performance of **one pitcher using one pitch type** across the loaded dataset.

The table will initially be game-independent and team-independent.

The primary source will be:

```text
curated.pitch
```

with relationships to the appropriate curated plate appearance, player, and pitch type records.

The analytics layer will derive metrics from the curated layer rather than directly querying the raw Statcast data.

The intended architecture is:

```text
raw.statcast_pitch
        │
        ▼
curated.pitch
        │
        ├───────────────┐
        ▼               ▼
curated.plate_appearance
        │
        ▼
analytics.player_pitch_type_effectiveness
```

---

# Analytical Grain

The table grain is:

```text
(player_id, pitch_type_id)
```

Therefore, there should be exactly one analytical row for each pitcher/pitch-type combination represented in the source data.

Examples:

```text
Pitcher A + Four-Seam Fastball
Pitcher A + Slider
Pitcher A + Changeup
Pitcher B + Four-Seam Fastball
Pitcher B + Curveball
```

The initial implementation will not include:

```text
game_id
team_id
season_id
```

This keeps the first version focused on overall pitch-type behavior.

Future analytics tables may introduce game, season, team, or split dimensions when those analytical questions are explicitly defined.

---

# Metric Definitions

## `pitches`

The total number of pitch records for the pitcher/pitch-type combination.

Definition:

```text
COUNT(curated.pitch)
```

Every qualifying pitch is counted exactly once.

---

## `plate_appearances`

The number of distinct plate appearances containing at least one pitch of the specified pitch type.

Definition:

```text
COUNT(DISTINCT plate_appearance_id)
```

This metric is intentionally named `plate_appearances` rather than `batters_faced`.

It does **not** represent the pitcher's traditional total batters-faced statistic.

For example, if a batter sees five pitches and two of those pitches are sliders, that plate appearance contributes:

```text
plate_appearances = 1
```

to the pitcher's slider row.

It does not contribute two plate appearances.

---

## `swings`

A pitch is classified as a swing when its pitch outcome is one of:

```text
foul
foul_bunt
foul_tip
hit_into_play
missed_bunt
swinging_strike
swinging_strike_blocked
```

Therefore:

```text
swings =
    foul
  + foul_bunt
  + foul_tip
  + hit_into_play
  + missed_bunt
  + swinging_strike
  + swinging_strike_blocked
```

---

## `whiffs`

A whiff is a swinging strike, including blocked swinging strikes.

Qualifying outcomes:

```text
swinging_strike
swinging_strike_blocked
```

Therefore:

```text
whiffs =
    swinging_strike
  + swinging_strike_blocked
```

---

## `called_strikes`

A called strike is a pitch with the outcome:

```text
called_strike
```

Definition:

```text
called_strikes =
    COUNT(outcome_type = 'called_strike')
```

---

## `balls_in_play`

A pitch is considered a ball in play when its outcome is:

```text
hit_into_play
```

Definition:

```text
balls_in_play =
    COUNT(outcome_type = 'hit_into_play')
```

---

## `fouls`

A foul is any of the following pitch outcomes:

```text
foul
foul_bunt
foul_tip
```

Therefore:

```text
fouls =
    foul
  + foul_bunt
  + foul_tip
```

---

# Plate Appearance Outcome Metrics

Some metrics cannot be determined from the individual pitch outcome alone.

For example, the pitch that ends a plate appearance may have a pitch outcome of `hit_into_play`, while the plate appearance itself determines whether that result was a single, double, home run, etc.

Therefore, these metrics will use the relationship between:

```text
curated.pitch
        ↓
curated.plate_appearance
```

The resulting plate-appearance outcome is attributed to the pitch type of the pitch associated with that outcome.

---

## `hits_allowed`

A hit is defined as a plate appearance outcome of:

```text
single
double
triple
home_run
```

Therefore:

```text
hits_allowed =
    single
  + double
  + triple
  + home_run
```

Only the pitch associated with the resulting plate-appearance outcome receives credit for the hit.

For example:

```text
Slider
    ↓
hit_into_play
    ↓
home_run
```

The slider receives:

```text
hits_allowed += 1
home_runs_allowed += 1
```

Previous pitches in the same plate appearance do not receive hit credit.

---

## `home_runs_allowed`

A home run is attributed to the pitch associated with a plate appearance whose outcome is:

```text
home_run
```

Definition:

```text
home_runs_allowed =
    COUNT(PA outcome = 'home_run')
```

---

## `strikeouts`

A strikeout is attributed to the pitch associated with a plate appearance whose outcome is:

```text
strikeout
```

Definition:

```text
strikeouts =
    COUNT(PA outcome = 'strikeout')
```

This measures strikeouts completed with the specified pitch type.

---

## `walks`

A walk is attributed to the pitch associated with a plate appearance whose outcome is:

```text
walk
```

Definition:

```text
walks =
    COUNT(PA outcome = 'walk')
```

---

## `hit_by_pitch`

A hit by pitch is attributed to the pitch associated with a plate appearance whose outcome is:

```text
hit_by_pitch
```

Definition:

```text
hit_by_pitch =
    COUNT(PA outcome = 'hit_by_pitch')
```

---

# Derived Rate Metrics

## `whiff_rate`

The percentage of swings that result in a whiff.

```text
whiff_rate = whiffs / swings
```

If `swings = 0`, the rate is undefined and should be represented as `NULL` rather than zero.

---

## `called_strike_rate`

The percentage of pitches resulting in called strikes.

```text
called_strike_rate = called_strikes / pitches
```

If `pitches = 0`, the rate is undefined and should be represented as `NULL`.

---

## `swing_rate`

The percentage of pitches at which the batter swings.

```text
swing_rate = swings / pitches
```

If `pitches = 0`, the rate is undefined and should be represented as `NULL`.

---

## `contact_rate`

The percentage of swings that result in contact.

For this initial implementation, contact is defined as:

```text
contact = swings - whiffs
```

Therefore:

```text
contact_rate = (swings - whiffs) / swings
```

If `swings = 0`, the rate is undefined and should be represented as `NULL`.

This is equivalent to:

```text
1 - whiff_rate
```

when swings are greater than zero.

---

## `strikeout_rate`

The percentage of plate appearances containing the pitch type that result in a strikeout.

```text
strikeout_rate = strikeouts / plate_appearances
```

If `plate_appearances = 0`, the rate is undefined and should be represented as `NULL`.

This metric intentionally uses plate appearances rather than pitches as its denominator.

---

# Initial Analytics Schema

The initial table will contain the following dimensions and measures.

### Dimensions

```text
player_id
pitch_type_id
```

### Aggregate Measures

```text
pitches
plate_appearances
balls_in_play
swings
whiffs
called_strikes
fouls
hits_allowed
home_runs_allowed
strikeouts
walks
hit_by_pitch
```

### Derived Measures

```text
whiff_rate
called_strike_rate
swing_rate
contact_rate
strikeout_rate
```

---

# Metrics Explicitly Deferred

The following metrics are intentionally excluded from the initial implementation:

```text
run_value
wOBA
xwOBA
CSW%
ERA
FIP
BABIP
hard_hit_rate
barrel_rate
exit_velocity
launch_angle
```

These metrics may be added later when their source fields, definitions, and analytical methodology have been explicitly established.

In particular, metrics such as `xwOBA`, `run_value`, and `CSW%` should not be approximated simply to populate the first version of the table.

---

# Null and Division Handling

Rate metrics must use safe division.

A denominator of zero should produce:

```text
NULL
```

rather than:

```text
0
```

This distinction is important.

For example, a pitch type with zero swings has an undefined whiff rate:

```text
whiffs = 0
swings = 0

whiff_rate = NULL
```

It should not be interpreted as:

```text
whiff_rate = 0%
```

---

# Data Integrity Expectations

The following relationships should hold for every row:

```text
whiffs <= swings
swings <= pitches
balls_in_play <= pitches
called_strikes <= pitches
fouls <= swings
hits_allowed <= balls_in_play
home_runs_allowed <= hits_allowed
strikeouts <= plate_appearances
walks <= plate_appearances
hit_by_pitch <= plate_appearances
```

Additionally:

```text
contact_rate = 1 - whiff_rate
```

when `swings > 0`.

All aggregate values must be non-negative integers.

Rate values should fall within:

```text
0.0 <= rate <= 1.0
```

---

# Rationale

This design intentionally separates **raw event counts** from **derived baseball rates**.

The counts provide auditable facts about what occurred:

```text
pitches
swings
whiffs
called_strikes
balls_in_play
...
```

The rates provide analytical interpretations of those facts:

```text
whiff_rate
swing_rate
contact_rate
...
```

This makes the analytics table easier to validate and allows the underlying event counts to remain available for future calculations.

The design also keeps the first version narrowly scoped. More advanced metrics can be added after their definitions and source requirements are established.

---

# Consequences

### Positive

* Establishes an explicit analytical grain.
* Makes baseball metric definitions reproducible.
* Prevents metric definitions from being buried inside loader code.
* Uses the curated layer as the authoritative analytics source.
* Provides both auditable counts and useful derived rates.
* Creates a foundation for future pitch-level intelligence.
* Makes unit and database validation straightforward.

### Trade-offs

* The initial table is aggregate and cannot answer game-specific questions.
* Some advanced Statcast metrics are deferred.
* Plate-appearance outcome metrics require joining pitch and plate-appearance data.
* A pitcher using the same pitch type across multiple teams is aggregated together in this initial version.

---

# Future Extensions

Potential future dimensions include:

```text
season_id
team_id
game_id
```

Potential future metrics include:

```text
walk_rate
hit_rate
home_run_rate
CSW%
run_value
wOBA_allowed
xwOBA
hard_hit_rate
barrel_rate
average_exit_velocity
```

Potential future analytical grains include:

```text
(player_id, season_id, pitch_type_id)
(player_id, team_id, pitch_type_id)
(game_id, player_id, pitch_type_id)
```

These should be introduced as separate analytical requirements rather than modifying the initial grain without justification.

---

# Implementation Sequence

Following this decision, implementation should proceed in this order:

1. Create the Alembic migration.
2. Create `analytics.player_pitch_type_effectiveness`.
3. Implement extraction from curated tables.
4. Implement transformation and metric calculations.
5. Add unit tests for metric definitions.
6. Implement the analytics loader.
7. Run rollback/migration validation.
8. Perform the initial permanent load.
9. Run database-level validation.
10. Commit and merge the completed feature.

---

## Decision Summary

The platform will initially model pitch-type effectiveness at:

```text
(player_id, pitch_type_id)
```

using curated pitch and plate-appearance data.

The first version will focus on:

```text
pitch volume
swing behavior
whiff behavior
contact behavior
called strikes
balls in play
fouls
hits
home runs
strikeouts
walks
hit by pitch
```

with derived rates for:

```text
whiff rate
called strike rate
swing rate
contact rate
strikeout rate
```

Advanced metrics will be added only after their definitions and source requirements have been explicitly established.
