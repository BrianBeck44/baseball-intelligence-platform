# ADR-005: Competition-Adjusted OPS (CA-OPS)

**Status:** Proposed
**Date:** 2026-10-27
**Decision Type:** Analytics / Data Modeling

## Context

The platform already materializes conventional batter-season OPS on:

```text
analytics.player_season_batting
```

That OPS does not account for the quality of opposing pitchers. Two hitters with the same observed OPS may have faced materially different pitching.

The next analytics capability is a custom, retrospective batter-season statistic:

```text
Competition-Adjusted OPS (CA-OPS)
```

CA-OPS is not an official MLB statistic. It is not a projection of future performance. It describes a completed season by adjusting observed OPS for the pitchers faced.

ADR-004 deferred league-adjusted batting metrics to a later decision. This ADR is that decision for v1.

Existing pitching analytics tables cannot supply pitcher OPS allowed. `analytics.player_game_pitching` and `analytics.player_season_pitching` store batters faced, hits allowed, home runs allowed, walks, hit by pitch, and strikeouts. They do not store singles, doubles, triples, at-bats, or sacrifice flies, so OPS allowed cannot be computed from those tables without inventing missing components.

---

## Decision

Create a derived analytics table:

```text
analytics.player_season_ca_ops
```

at grain:

```text
(player_id, season_id)
```

Each row is one batter's season CA-OPS across all teams.

Do not add CA-OPS columns to `analytics.player_season_batting` or change existing batting or pitching metric definitions.

Do not modify curated facts.

Reuse the existing authoritative batting-outcome increment matrix. Do not create a competing outcome mapping.

---

# Purpose

CA-OPS answers:

```text
How does this batter's season OPS compare with what the pitchers faced
typically allow, after recentering on the same-season league?
```

Equivalent form:

```text
CA-OPS = leave-one-batter-out league OPS
       + (observed batter OPS − expected opponent OPS)
```

A batter who posts the same OPS against stronger-than-average pitchers should receive a higher CA-OPS. A batter who posts the same OPS against weaker-than-average pitchers should receive a lower CA-OPS.

---

# Data Flow

```text
curated.plate_appearance
curated.outcome_type
curated.game
        │
        ▼
pitcher-season and batter-pitcher
matchup counting statistics
        │
        ▼
leave-one-batter-out pitcher OPS allowed
leave-one-batter-out league OPS
        │
        ▼
shrunk, PA-weighted expected opponent OPS
        │
        ▼
analytics.player_season_batting.ops
        │
        ▼
analytics.player_season_ca_ops
```

The batter's observed OPS is taken from `analytics.player_season_batting.ops`. It is not re-derived from plate appearances.

Pitcher-quality counting statistics are derived from curated plate appearances because the existing pitching analytics tables cannot compute OPS allowed.

The increment matrix remains the one already implemented for game-level batting. Re-stating baseball outcome rules here would create a second mapping.

---

# Analytical Grain

The persisted product grain is:

```text
(player_id, season_id)
```

`player_id` is the batter. `season_id` comes from `curated.game.season_id`.

The first version does not include:

```text
team_id
game_id
game_type_id
pitcher_id
```

A player who bats for multiple teams in the same season still produces one CA-OPS row.

The computation uses two intermediate grains that are not required to be persisted as public analytics products:

```text
(season_id, pitcher_id)
(season_id, batter_id, pitcher_id)
```

---

# Source Mapping

### Observed batter OPS

```text
analytics.player_season_batting.ops
```

joined to the CA-OPS row on `(player_id, season_id)`.

If that stored OPS is NULL, CA-OPS is NULL. A missing OPS is not replaced with zero.

### Matchup and pitcher counting statistics

```text
curated.plate_appearance
    JOIN curated.game
      ON curated.game.game_id = curated.plate_appearance.game_id
    LEFT JOIN curated.outcome_type
      ON curated.outcome_type.id = curated.plate_appearance.outcome_type_id
```

Required fields:

```text
curated.plate_appearance.batter_id
curated.plate_appearance.pitcher_id
curated.plate_appearance.game_id
curated.outcome_type.code          -- NULL when outcome_type_id is NULL
curated.game.season_id
```

Every curated plate appearance in the season is eligible. The current curated population is already regular-season Statcast (`game_type = 'R'`). v1 does not add a further game-type filter, minimum-PA filter, or team filter.

Unknown non-null outcome codes must fail in the same way as game-level batting: raise `ValueError`. They are not dropped silently.

---

# Pitcher Attribution

v1 uses the pitcher stored on:

```text
curated.plate_appearance.pitcher_id
```

The current plate-appearance extract assigns that column from the first pitch of the plate appearance (`MIN(pitch_number)`). The terminal pitch supplies batter context.

A pitching change during a plate appearance can therefore attribute the completed result to the first pitcher rather than the pitcher who threw the deciding pitch.

That difference is a known v1 limitation. It is accepted so CA-OPS uses the same pitcher identity as `analytics.player_game_pitching`. v1 will not re-read `raw.statcast_pitch` to recover a terminal pitcher. `curated.pitch` has no `pitcher_id` and cannot supply that attribution.

---

# Outcome Counting Rules

Plate appearances do not store singles, doubles, triples, home runs, walks, hit-by-pitch, sacrifice flies, or at-bats as columns. Those counts are derived from `curated.outcome_type.code` using the existing batting increment matrix in `backend/app/analytics/player_game_batting_data.py`.

v1 must reuse that matrix. In particular:

* `walk` and `intent_walk` both increment walks. There is no separate IBB column.
* `sac_fly` and `sac_fly_double_play` increment sacrifice flies.
* `strikeout` and `strikeout_double_play` increment strikeouts.
* `catcher_interf`, `truncated_pa`, and `NULL` outcomes increment plate appearances only.
* Every curated plate appearance increments plate appearances by 1, including incomplete outcomes.

Those PA-only outcomes remain in PA weights. They do not contribute hits, at-bats, walks, hit-by-pitch, or sacrifice flies.

OPS, OBP, and SLG use the same formulas as `analytics.player_season_batting`:

```text
on_base_percentage =
    (hits + walks + hit_by_pitch)
    / (at_bats + walks + hit_by_pitch + sacrifice_flies)

total_bases =
    singles + (2 * doubles) + (3 * triples) + (4 * home_runs)

slugging_percentage = total_bases / at_bats

ops = on_base_percentage + slugging_percentage
```

A denominator of zero produces NULL, not 0. OPS is NULL unless both OBP and SLG are non-NULL.

---

# Leave-One-Batter-Out Baseline

For target batter `b` in season `s`, exclude every plate appearance where:

```text
batter_id = b
```

from:

1. Each opponent pitcher's season counting statistics and OPS allowed.
2. The season league OPS baseline used for that batter's opponent-quality estimates and CA-OPS recentering.

The league OPS for batter `b` is therefore the aggregate OBP + SLG of all other batters' eligible plate appearances in that season. It is not the average of individual pitcher OPS-allowed values, and it is not the league OPS that still includes batter `b`.

If that leave-one-out league OPS is NULL, CA-OPS is NULL.

---

# Shrunk Pitcher OPS Allowed

For each pitcher `p` faced by batter `b`, recompute OPS allowed from the remaining plate appearances after excluding `b`.

Let:

```text
n  = remaining plate appearances for pitcher p after excluding batter b
k  = 150     # documented v1 prior-strength constant
lg = leave-one-batter-out league OPS for batter b
ops_p = OPS allowed for pitcher p after excluding batter b
```

Then:

```text
if n = 0 or ops_p is NULL:
    shrunk_ops_p = lg
else:
    shrunk_ops_p = (n * ops_p + k * lg) / (n + k)
```

`k = 150` is a documented v1 constant. It is not fitted per season. Changing `k` is a later decision.

`n = 0` occurs when pitcher `p` faced only batter `b` in that season. The leave-one-out league baseline is used. It is not treated as a zero OPS allowed.

`ops_p` is NULL when the remaining plate appearances do not define both OBP and SLG. v1 substitutes `lg` rather than converting the missing OPS to zero and rather than dropping the batter's plate appearances against that pitcher.

Shrinkage applies to opponent quality. v1 does not shrink the batter's observed OPS.

---

# Expected Opponent OPS and CA-OPS

Let `PA_b,p` be batter `b`'s plate appearances against pitcher `p` in the season, including PA-only outcomes.

```text
expected_opponent_ops_b =
    SUM(PA_b,p * shrunk_ops_p) / SUM(PA_b,p)
```

over pitchers faced. If the batter has no plate appearances, expected opponent OPS and CA-OPS are NULL.

Then:

```text
CA-OPS_b = lg_b + (OPS_b − expected_opponent_ops_b)
```

where `OPS_b` is `analytics.player_season_batting.ops` and `lg_b` is the leave-one-batter-out league OPS.

This is equivalent to:

```text
CA-OPS_b = OPS_b + (lg_b − expected_opponent_ops_b)
```

### Direction of the adjustment

`expected_opponent_ops` is lower when the batter faced pitchers who allow less offense than the leave-one-out league. Subtracting a lower expected value from observed OPS produces a larger residual, so CA-OPS rises relative to observed OPS.

`expected_opponent_ops` is higher when the batter faced pitchers who allow more offense than the leave-one-out league. The residual shrinks, so CA-OPS falls relative to observed OPS.

Facing league-average shrunk pitcher quality yields `expected_opponent_ops ≈ lg`, so CA-OPS ≈ observed OPS.

---

# Nulls and Data Quality

* If `analytics.player_season_batting.ops` is NULL, CA-OPS is NULL.
* If leave-one-out league OPS is NULL, CA-OPS is NULL.
* If expected opponent OPS cannot be formed because the batter has no plate appearances, CA-OPS is NULL.
* Division by zero in OBP or SLG produces NULL, never 0.
* Missing values are not converted to zero.
* Incomplete outcomes (`NULL` `outcome_type_id`, `truncated_pa`, `catcher_interf`) remain in the population as plate appearances. They do not invent hits, at-bats, or walks.
* Ambiguous source plate appearances that already fail curated extract (conflicting `events`, missing required context) never reach this metric. v1 does not add a second silent-drop rule on top of that extract.
* Unknown non-null outcome codes fail fast.
* First-pitcher attribution can mis-assign a mid-PA pitching change. That limitation is documented; those plate appearances are not dropped.

v1 does not omit a `player_season_batting` row from `player_season_ca_ops` solely because CA-OPS is NULL. The row is stored with NULL CA-OPS.

---

# Limitations

OPS is not linear in run value. OBP and SLG are added with equal weight even though they do not contribute equally to runs.

Pitcher OPS allowed is affected by the hitters those pitchers faced, parks, defense, sequencing, and luck. Leave-one-out removes only the target batter, not the rest of the lineup or context.

v1 does not adjust for:

```text
park
defense
platoon
luck / BABIP
linear weights / wOBA / wRC+
game type splits
team splits
```

CA-OPS is descriptive of a completed season. It is not a forecast, a talent estimate, or a playing-time projection. Using it to predict future performance would require additional regression to the mean, aging, and role assumptions that are out of scope.

---

# Initial Analytics Schema

### Dimensions

```text
player_id
season_id
```

### Measures

Exact physical column names will be chosen at implementation. The first version must persist enough to reconstruct and validate the metric, including:

```text
observed_ops                 -- from player_season_batting.ops
league_ops                   -- leave-one-batter-out league OPS
expected_opponent_ops        -- PA-weighted shrunk pitcher OPS allowed
ca_ops
plate_appearances            -- batter PA used as weights
```

`created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP` follows existing analytics tables.

Rate columns are nullable. A denominator of zero or a missing observed OPS yields NULL, not 0.

Foreign keys:

```text
player_id → curated.player.player_id
season_id → curated.season.season_id
```

Primary key:

```text
(player_id, season_id)
```

Do not change the definitions of existing analytics tables to accommodate this metric.

---

# Load Behavior

The caller owns the transaction.

The table is derived state and must be safely rebuildable. Reruns must refresh existing rows rather than accumulate values.

The loader will use PostgreSQL upsert on `(player_id, season_id)`.

The CA-OPS loader must run after `analytics.player_season_batting` is current, because observed OPS is read from that table.

Empty source input must not fail and must not insert rows.

The first implementation must not query raw Statcast.

---

# Implementation Sequence

Following this decision, implementation should proceed in this order:

1. Create the Alembic migration for `analytics.player_season_ca_ops`.
2. Implement extraction of eligible plate appearances from `curated.plate_appearance`, `curated.outcome_type`, and `curated.game`.
3. Implement transformation: reuse the batting increment matrix; build pitcher-season and batter-pitcher totals; apply leave-one-out league OPS, `k = 150` shrinkage, PA-weighted expected opponent OPS, and CA-OPS.
4. Read observed OPS from `analytics.player_season_batting`; do not recompute it.
5. Add focused unit tests for leave-one-out identity, shrinkage, `n = 0`, NULL OPS, PA-only outcomes, unknown outcome codes, and the direction of the opponent-quality adjustment.
6. Implement the analytics loader and integrate it into `load_all_analytics` after season batting.
7. Create a rollback-only validation script that uses `TEST_DATABASE_URL` / `baseball_intelligence_test` only.
8. Do not reload development data until that validation has passed.

Do not implement frontend or API surfaces in the first implementation unless a later decision asks for them.

---

# Alternatives Considered

### Add CA-OPS columns onto `analytics.player_season_batting`

This would mix conventional batting facts with a custom adjustment.

Rejected because ADR-004 defined that table as a rollup of game-level batting counts plus conventional rates. A separate derived table keeps those definitions stable.

### Compute pitcher OPS allowed from `analytics.player_season_pitching`

This would avoid reading plate appearances.

Rejected because that table cannot produce OBP or SLG. Filling missing components would invent baseball facts.

### Use the terminal pitcher for plate-appearance credit

This would better match “pitcher of record” for the result.

Rejected for v1 because `curated.plate_appearance.pitcher_id` is first-pitch attribution, `curated.pitch` has no pitcher, and existing pitching analytics already use the stored pitcher. Changing attribution would require a curated-model change or a raw-layer read.

### Use full-season pitcher OPS allowed without excluding the target batter

This is simpler.

Rejected because the batter's own production would be included in the opponent-quality estimate.

### Average individual pitcher OPS-allowed values for the league baseline

This would treat a 20-PA reliever and a 700-PA starter equally.

Rejected. League OPS is the aggregate OBP + SLG of eligible plate appearances.

### Skip shrinkage

This would keep the formula closer to the original hypothesis.

Rejected because small-sample pitcher OPS allowed is too noisy to use as a schedule adjustment.

### Shrink the batter's observed OPS

This is common in projection systems.

Rejected for v1. CA-OPS is a retrospective description of the season the batter already produced, not a talent estimate.

### wOBA / wRC+ instead of OPS

Linear weights would be more defensible as a run estimator.

Rejected for v1 because the agreed product is an OPS adjustment, and the platform does not yet have an adopted linear-weights model.

---

# Consequences

### Positive

* Documents a custom metric before any table or loader exists.
* Keeps conventional batting OPS unchanged.
* Reuses the existing outcome matrix.
* Makes leave-one-out, shrinkage, and first-pitcher attribution explicit.
* Distinguishes missing rates from zeros.

### Trade-offs

* First-pitcher attribution can differ from terminal-pitcher credit.
* OPS remains a coarse run proxy.
* Opponent quality is still contaminated by other hitters and context.
* `k = 150` is a chosen prior, not an estimated hyperparameter.
* Implementation must read plate appearances even though batter OPS is already stored.

---

# Future Extensions

Potential later work, each a separate decision:

```text
terminal-pitcher attribution
park adjustment
platoon splits
wOBA / wRC+ analog
team or game-type grains
API and frontend comparison
estimated rather than chosen shrinkage k
```

---

## Decision Summary

The platform will model v1 CA-OPS at:

```text
(player_id, season_id)
```

in `analytics.player_season_ca_ops`.

Observed OPS comes from `analytics.player_season_batting.ops`. Pitcher and matchup counts come from curated plate appearances using the existing batting increment matrix. Each batter's opponent-quality estimates and league baseline exclude that batter's plate appearances. Pitcher OPS allowed is shrunk toward that leave-one-out league OPS with `k = 150`. CA-OPS is that league OPS plus the residual of observed OPS over PA-weighted expected opponent OPS.

The metric is a retrospective season description. It is not an official statistic and not a projection.

---

*Related: ADR-004 — Player Season Batting Analytics*
