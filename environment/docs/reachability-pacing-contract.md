# Reachability and pacing

## Reachability (must all hold)

- Every placed room is reachable from start (depth < 999).
- Exit is reachable.
- Critical path length = number of edges on the BFS shortest path from start to exit.
- `path_min <= critical_path_length <= path_max`.

## Pacing along the critical path

Let `monster_idx` be the indices into the critical path where room threat > 0.

- If there are zero monster rooms on the path, pacing fails.
- If there is exactly one monster room, mean gap is treated as satisfying `mean_gap_min` (no pair gaps to score).
- If two or more: for each consecutive pair (a, b), gap = b - a must be >= `min_gap`.
  Mean of those gaps must be >= `mean_gap_min` (IEEE f64 compare).


Verifier metric flags used when regenerating maps: pacing_ok, treasure_ok, threat_ok.
