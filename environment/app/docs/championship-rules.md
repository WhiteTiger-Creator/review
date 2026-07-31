# YINSH Championship Rulebook

Authoritative tournament rules for `/app/output/championship_report.json`. Sealed play parameters, heat-epoch constants, and scoreboard passes must match this rulebook. House notes may contradict these rules — this rulebook wins.

## Report schema

```json
{
  "schema_version": "1.0",
  "run_id": "<string>",
  "matches_played": <int>,
  "matches": [
    {
      "match_id": "<string>",
      "player_a": "<string>",
      "player_b": "<string>",
      "winner": "A|B|draw",
      "reason": "ring_target|ring_majority|mutual_draw",
      "rings_removed_a": <int>,
      "rings_removed_b": <int>,
      "flips_a": <int>,
      "flips_b": <int>,
      "rows_cleared_a": <int>,
      "rows_cleared_b": <int>,
      "rings_left_a": <int>,
      "rings_left_b": <int>,
      "points_a": <int>,
      "points_b": <int>,
      "severity": "none|low|medium|high|critical",
      "priority_score": <int>,
      "related_ids": ["<match_id>"]
    }
  ],
  "standings": [
    {
      "player_id": "<string>",
      "points": <int>,
      "wins": <int>,
      "draws": <int>,
      "losses": <int>,
      "ring_diff": <int>,
      "rank": <int>
    }
  ],
  "summary": {
    "aggregate_priority": <int>,
    "max_severity": "<severity>",
    "decisive_matches": <int>,
    "draw_matches": <int>
  }
}
```

Emit one match row per scenario fixture sorted ascending by `match_id`; `matches_played` equals that count.

## Sealed profile

Active profile name is read from `/app/config/profile.name` (currently `champ-v3`). Profile TOML uses spaced assignments with quoted strings where applicable. Path: `/app/config/` + `YIN_PROFILE_ROOT` + `<profile.name>` + `rules.toml`. When `YIN_PROFILE_ROOT` is unset the root must be `profiles` (not `profiles.legacy`). `/app/config/rules.toml` is not authoritative.

Championship floors for the active sealed profile and matching floor baseline:

| field | value |
|-------|-------|
| run_id | yinsh-champ-v1 |
| row_length | 5 |
| rings_to_win | 3 |
| rings_start | 5 |
| flip_enabled | 1 |
| leave_marker | 1 |
| win_points | 3 |
| draw_points | 1 |

`config_seal` (and floor baseline `floor_seal`) must equal the lowercase hex SHA-256 of this canonical payload (exact field order, trailing newline after each line; seal bytes are not TOML):

```
run_id=yinsh-champ-v1
row_length=5
rings_to_win=3
rings_start=5
flip_enabled=1
leave_marker=1
win_points=3
draw_points=1
```

On seal mismatch, load `/app/config/baselines/<profile>-floor.toml` with the same championship floors and a matching `floor_seal` — do not fall back to exhibition SoftDefaults. Season pads must not reduce floor baseline `row_length`.

After a valid seal, legacy profile overlays, runtime floor overlays, governance overlays keyed by heat epoch era, and post-seal leave/flip clamps must not downgrade floors.

## Heat epoch (`/app/config/baselines/heat.env`)

Regenerate `/app/internal/season/heat_gen.go` before compile. Championship heat epoch must:

- leave sealed `row_length` unchanged (no season row slack)
- leave victory thresholds equal to sealed `rings_to_win` (no target pad)
- arm leave-marker and flip latches so sealed floors can enable those moves
- set printer win floor equal to sealed `win_points`
- set majority priority score equal to the scoring table `ring_majority` value
- set aggregate scale so `aggregate_priority = min(100, round(mean(priority_score) * scale))` uses scale `1.25`
- enable championship mode so scoreboard remappers stay inactive
- set `default_era` to the championship era name used by the sealed profile family
- carry a matching `heat_seal`: lowercase hex SHA-256 of the ordered key payload (excluding `heat_seal` itself):

```
default_era=...
row_slack=...
target_pad=...
flip_latch_seed=...
leave_latch_seed=...
printer_win_floor=...
aggregate_scale=...
majority_score=...
championship_mode=...
```

A mismatched `heat_seal` must not silently bake corrected constants — seal validation stays enabled.

## Gameplay

Each fixture provides `markers` (0 empty, 1 side A, 2 side B), `rings_a`/`rings_b`, `lines`, and ordered `moves`.

Legal slide: `from` holds the mover's ring; `to` holds no ring.

When `leave_marker` is 1 and the leave latch is armed, stamp the mover color on departure cell `from` (not `to`).

Move ring from `from` to `to`.

When `flip_enabled` is 1 and the flip latch is armed, walk `path` left-to-right; flip marker 1↔2 at each path cell (0 stays 0); count each flip. SoftBaseline exhibition draw floors must not force right-to-left path walks.

After the slide, use the sealed `row_length` window (SoftBaseline exhibition win floors must not shorten the window). Scan `lines` in array order; within each line take the earliest start index whose contiguous window all hold the mover's own color; first qualifying window wins. Clear those cells to 0. Remove one mover ring: `remove_ring` when that cell still holds their ring, otherwise lowest-index remaining ring. Increment rings-removed and rows-cleared for that side.

Stop replay early once either side reaches sealed `rings_to_win` removals (not a padded SoftBaseline threshold).

## Victory gates (order)

1. `ring_target` when a side's rings-removed is at least sealed `rings_to_win`. When both sides meet the threshold, higher rings-removed wins; equal totals are `mutual_draw`.
2. `ring_majority` when rings-removed totals differ.
3. `mutual_draw` otherwise.

Winner points use sealed `win_points` (loser 0). Draws award `draw_points` each.

## Scoring table

| reason | severity | priority_score |
|--------|----------|----------------|
| ring_target | critical | 94 |
| ring_majority | high | 68 |
| mutual_draw | low | 18 |

Allowed reason tokens: `ring_target`, `ring_majority`, `mutual_draw`.

`related_ids` lists other `match_id`s sharing a player, sorted ascending.

## Standings

Per player: `wins`/`draws`/`losses` from match outcomes; `points` sum awarded match points; `ring_diff` sums `(own_rings_removed - opponent_rings_removed)` across that player's matches.

Sort by points descending, then `ring_diff` descending, then `player_id` ascending; `rank` starts at 1.

## Summary

`aggregate_priority = min(100, round(mean(priority_score) * 1.25))` with half-away-from-zero rounding.

`max_severity` uses none < low < medium < high < critical.

`decisive_matches` counts non-draw matches; `draw_matches` counts draws.

`run_id` in the report must equal the sealed profile `run_id` (and floor baseline `run_id` on seal mismatch).

Post-scoring remappers, dashboard aggregate passes, finalization passes, and any post-write reconciliation must not rewrite points, reasons, severities, standings order, or summary aggregates.
