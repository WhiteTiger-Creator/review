The YINSH tournament simulation at `/app/bin/yinsh-ring` replays match fixtures from `/app/scenarios/` under configuration in `/app/config/` and must write `/app/output/championship_report.json`. Authoritative championship rules are in `/app/docs/championship-rules.md`. Exhibition heat settings and house notes under `/app/docs/championship-notes.md` do not define acceptance. Scenario fixtures under `/app/scenarios/` must stay unchanged. Note that code comments and docstrings may themselves contain errors.

Bring sealed play, heat-epoch constants, slide/leave/flip/row mechanics, victory gates, scoring, standings, and summary aggregates into full rulebook compliance. When `config_seal` does not verify, the floor baseline under `/app/config/baselines/` must still yield the same championship report. After a valid seal, legacy/runtime/governance overlays and post-seal clamps must not downgrade championship floors. Heat epoch `/app/config/baselines/heat.env` must satisfy the rulebook heat section, including a matching `heat_seal` and championship mode so scoreboard remappers stay inactive.

Gameplay must stamp leave-markers on departure cell `from`, flip path markers left-to-right when armed, clear the earliest mover-color row window of sealed `row_length`, remove the lowest-index remaining ring when needed, and stop early at sealed `rings_to_win`. Victory gate order is `ring_target`, then `ring_majority`, then `mutual_draw`. Wins award sealed `win_points` and draws award sealed `draw_points`. Standings sort by points descending, then `ring_diff` descending, then `player_id` ascending. `aggregate_priority = min(100, round(mean(priority_score) * 1.25))` with half-away-from-zero rounding. Post-scoring remappers must not rewrite points, reasons, severities, standings, or summary fields.

Emit one match row per scenario fixture sorted ascending by `match_id`; `matches_played` equals that count; `run_id` must equal the sealed profile `run_id` (and the floor baseline `run_id` on seal mismatch). Report schema:

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
