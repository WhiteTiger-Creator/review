# YINSH Championship Rulebook

Authoritative tournament rules for `/app/output/championship_report.json`. Sealed play parameters, heat-epoch constants, and scoreboard passes must match this rulebook.

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

## Sealed profile (`/app/config/profile.name` → `/app/config/profiles/<name>/rules.toml`)

Active profile name is read from `/app/config/profile.name` (currently `champ-v3`). Profile TOML uses spaced assignments with quoted strings where applicable.

Championship floors:

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

`config_seal` must equal the lowercase hex SHA-256 of this canonical payload (exact field order, trailing newline after each line; seal bytes are not TOML):

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

Seal value: `063467fd701342809041f9cbb843d8e83772f6076602cd1c772257a1cbd9095d`

Profile load path: `/app/config/` + `YIN_PROFILE_ROOT` + `<profile.name>` + `rules.toml`. When `YIN_PROFILE_ROOT` is unset the root must be `profiles` (not `profiles.legacy`). `/app/config/rules.toml` is not authoritative.

On seal mismatch, load `/app/config/baselines/<profile>-floor.toml` with the same championship floors and `floor_seal` matching the canonical payload SHA-256 above — do not fall back to exhibition SoftDefaults. Season pads from the heat epoch must not subtract from floor baseline row_length.

After a valid seal, none of the following may alter floors: `/app/config/profiles.legacy/<profile>/rules.toml`, `/app/config/runtime/<profile>.floor.toml`, governance overlays under `/app/config/runtime/` keyed by the heat epoch era, or post-seal soft/prefer clamps that force `flip_enabled` or `leave_marker` off.

## Heat epoch (`/app/config/baselines/heat.env`)

Regenerate `/app/internal/season/heat_gen.go` before rebuild. Championship values:

| key | value |
|-----|-------|
| default_era | champ-v3 |
| row_slack | 0 |
| target_pad | 0 |
| flip_latch_seed | 1 |
| leave_latch_seed | 1 |
| printer_win_floor | 3 |
| aggregate_scale | 1.25 |
| majority_score | 68 |
| championship_mode | 1 |

Build-time latch seeds must arm leave-marker and flips together with sealed floors. `championship_mode` must enable championship scoring passes (no exhibition point remap or reason demotion).

## Gameplay

Each fixture provides `markers` (0 empty, 1 side A, 2 side B), `rings_a`/`rings_b`, `lines`, and ordered `moves`.

Legal slide: `from` holds the mover's ring; `to` holds no ring.

When `leave_marker` is 1, stamp the mover color on departure cell `from` (not `to`); honor sealed floor together with the build-time leave latch (seed 1).

Move ring from `from` to `to`.

When `flip_enabled` is 1, walk `path` left-to-right; flip marker 1↔2 at each path cell (0 stays 0); count each flip; honor sealed floor together with build-time flip latch (seed 1).

After the slide, scan `lines` in array order; within each line take the earliest start index whose contiguous window of exactly `row_length` cells all hold the mover's own color; first qualifying window wins. Clear those cells to 0. Remove one mover ring: `remove_ring` when that cell still holds their ring, otherwise lowest-index remaining ring. Increment rings-removed and rows-cleared for that side.

Stop replay early once either side reaches `rings_to_win` removals (sealed value, not padded threshold).

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

Post-scoring remappers, dashboard aggregate passes, finalization passes, and any post-write reconciliation must not rewrite points, reasons, severities, standings order, or summary aggregates (including demoting `ring_target` to `ring_majority` or reclobbering `aggregate_priority`).
