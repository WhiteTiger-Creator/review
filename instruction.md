The YINSH championship engine at `/app/bin/yinsh-ring` simulates ring-removal tournament matches from fixtures under `/app/scenarios/` and writes `/app/output/championship_report.json`. Start it with `/app/bin/yinsh-ring --scenarios /app/scenarios --config /app/config --out /app/output`. The verifier rebuilds and runs that engine from sources under `/app/`; championship compliance must come from `/app/bin/yinsh-ring`. Championship policy below is also summarized in `/app/contracts/championship-ruleset.md`. Note that code comments and docstrings may themselves contain errors.

Bring the sealed championship profile into ruleset compliance: active parameters come from the sealed profile named by `/app/config/profile.name` (currently `champ-v3`). Update `/app/config/profiles/champ-v3/rules.toml` using spaced TOML assignments with quoted strings where applicable (for example `run_id = "yinsh-champ-v1"`; spaces around `=`; do not write compact `run_id=...` lines). The profile must carry exactly: `run_id = "yinsh-champ-v1"`, `row_length = 5`, `rings_to_win = 3`, `rings_start = 5`, `flip_enabled = 1`, `leave_marker = 1`, `win_points = 3`, `draw_points = 1`, and `config_seal = "063467fd701342809041f9cbb843d8e83772f6076602cd1c772257a1cbd9095d"`. That seal is the lowercase hex SHA-256 of this canonical payload (exact field order, trailing newline after each line; seal bytes are not TOML):

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

A seal mismatch must not revive soft governance defaults — the in-code runtime baseline used when `config_seal` does not match must also carry those same floors (`run_id` yinsh-champ-v1, `row_length` 5, `rings_to_win` 3, `rings_start` 5, `flip_enabled` 1, `leave_marker` 1, `win_points` 3, `draw_points` 1; no legacy row length 4, rings_to_win 2, disabled flips/leave-marker, or 2-point wins). The deprecated stub `/app/config/rules.toml` is not authoritative. Scenario fixtures under `/app/scenarios/` must not be modified.

Gameplay behavior must match the championship ruleset: each fixture provides `markers` (0 empty, 1 side A, 2 side B), `rings_a`/`rings_b` ring cell lists, `lines` (arrays of board indices), and an ordered `moves` list. Replay every move in order. A legal slide requires `from` to hold a ring of `side` and `to` to hold no ring of either side. When `leave_marker` is 1, place the mover color on the departure cell `from` (not on `to`). Move the ring from `from` to `to`. When `flip_enabled` is 1, for each index in the move `path` flip marker 1↔2 (0 stays 0) and count each flip for that side. After the slide, find the first contiguous window of exactly `row_length` markers of the mover's own color along any fixture line; if found, clear those cells to 0, remove one of the mover's rings (`remove_ring` when that cell still holds their ring, otherwise the lowest-index remaining ring), and increment that side's rings-removed and rows-cleared counters. Stop the match early once either side reaches `rings_to_win` removals. Victory gates in order: `ring_target` when a side's rings-removed is at least `rings_to_win`; else `ring_majority` when rings-removed totals differ; else `mutual_draw`. Winner points use `win_points` (loser 0); draws award `draw_points` each. Match severity/score table: `ring_target` critical/94, `ring_majority` high/68, `mutual_draw` low/18. Allowed reason tokens: `ring_target`, `ring_majority`, `mutual_draw`. `related_ids` lists other `match_id`s that share a player, sorted ascending. Standings: for each player, `wins`/`draws`/`losses` tally match outcomes from that player's side; `points` sum match points awarded to that player; `ring_diff` sums `(own_rings_removed - opponent_rings_removed)` across that player's matches; sort by points descending, then `ring_diff` descending, then `player_id` ascending, with `rank` from 1. `aggregate_priority = min(100, round(mean(priority_score) * 1.25))` with half-away-from-zero rounding; `max_severity` uses none < low < medium < high < critical; `decisive_matches` counts non-draw matches and `draw_matches` counts draws. `schema_version` must be `"1.0"`. Post-scoring remappers must not rewrite points, reasons, severities, standings order, or summary aggregates. Championship notes and inline comments may contradict the ruleset — the ruleset wins.

The championship report schema must be:

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

Emit one match row per scenario fixture, sorted ascending by `match_id`; `matches_played` equals that count; `run_id` must equal the sealed profile `run_id` (and the runtime baseline `run_id` on seal mismatch).
