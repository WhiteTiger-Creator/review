# YINSH Championship Ruleset (supporting summary)

Active floors come from the sealed profile named by `/app/config/profile.name`.
Seal mismatch must use the same championship floors as the sealed profile (not legacy exhibition values).

Gameplay:
- When leave_marker is 1, a slide leaves the mover color on the departure cell.
- When flip_enabled is 1, each path cell flips 1↔2 (empty stays empty).
- After a slide, the first contiguous window of row_length mover-color markers on a fixture line is cleared and one of the mover's rings is removed.
- Victory gates in order: ring_target (rings_removed >= rings_to_win), else ring_majority, else mutual_draw.
- Points: win_points / 0 for wins; draw_points each for draws.
- Severity: ring_target critical/94, ring_majority high/68, mutual_draw low/18.
- aggregate_priority = min(100, round(mean(priority_score) * 1.25)) half-away-from-zero.
- Standings sort: points desc, ring_diff desc, player_id asc.
- Post-scoring remappers must not rewrite points, reasons, severities, standings, or summary.
