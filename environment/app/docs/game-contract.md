# Tidefront adjudication contract

`/app/bin/tidefront adjudicate` resolves a complete deterministic match. It requires absolute paths for `--match`, `--stations`, `--catalog`, `--leaps`, and `--output`, plus a positive `--threads` value. Zero and negative worker counts must be rejected with failure; the forecast engine's legacy clamp to one worker is not compliant for this command and must be overridden. The command writes no standard output. It removes the destination before reading inputs and leaves no destination after any failure.

## Match input

The match is strict JSON. Duplicate keys, unknown fields, trailing values, and type substitutions are invalid. `schema_version` is `1`. `match_id` and `start_utc` are nonempty. `turn_count` is from 1 through 1000. `turn_seconds` is from 1 through 86400. At least two players, one node, and one fleet are required.

Player IDs are unique and nonempty. Initiative is a nonnegative integer. Node IDs are unique and nonempty. Every node references an existing station, has a finite `base_depth_m`, has an integer value from 0 through 1000000, and has either no owner or an existing player owner. Edges are undirected. Self edges, unknown endpoints, and duplicate undirected edges are invalid.

Fleet IDs are unique and nonempty. Every fleet references an existing player and node, has a finite nonnegative draft, and begins on a node not occupied by another fleet. Orders use turns from 1 through `turn_count`, reference an existing fleet, and are unique per fleet and turn. A missing order means `hold`. A `hold` order has no target. A `move` order has an existing `target_node_id`. No other order kind is valid.

## Tides and movement

The station bundle, constituent catalog, and leap table follow the public contracts in `/app/docs/station-bundle.md`, `/app/docs/catalog-format.md`, and `/app/docs/leap-table.md`. One tide sample is evaluated for every station and turn. Turn 1 uses `start_utc`; later turns advance by `turn_seconds` on the TAI timeline, so a declared leap second remains a distinct turn timestamp.

For a node, `tide_m` is its station sample rounded to six decimal places using round-to-nearest with ties to even. `effective_depth_m` is `base_depth_m + tide_m` rounded by the same rule. Negative zero is written as zero. Movement compares fleet draft against these rounded effective depths.

Each turn uses the fleet positions produced by the preceding turn; all sources, target occupants, and movement dependencies for the current turn are then evaluated from one start-of-turn snapshot. A move is a candidate only when the target differs from the current source, an edge connects source and target, and the fleet draft is less than or equal to both source and target effective depths. Same-node and nonadjacent moves are `blocked-edge` even when a depth check would also fail. Depth is checked only after the edge rule, producing `blocked-depth`. Only candidates enter target contests.

Candidate moves are resolved simultaneously. For each target node, one contender is selected by higher player initiative, then lexicographically smaller player ID, then lexicographically smaller fleet ID. Other contenders receive `blocked-contest` and remain at their sources. A selected move succeeds when its target was empty at the start of the turn or its start-of-turn occupant also has a selected move that succeeds. Thus a selected contest winner can still become `blocked-occupied`, and a contest loser or otherwise blocked occupant can stop every upstream dependency. Chains ending at an empty node and closed cycles, including swaps, succeed together. A chain ending at a fleet that does not have a selected successful move fails with `blocked-occupied`. Successful moves receive `moved`. Holds receive `hold`.

After all movement is applied simultaneously, each occupied node becomes owned by the occupying fleet's player. A vacated node retains its previous owner until a fleet occupies it on a later turn; a holding or blocked fleet still occupies and captures its current node. The turn score delta for a player is the sum of the values of all nodes that player owns after capture, including retained unoccupied territory, rather than only newly captured nodes. Scores are cumulative. The final winner is selected by higher final score, then higher initiative, then lexicographically smaller player ID.

## Result

The result is compact JSON followed by one newline. It contains exactly `schema_version`, `game`, `match_id`, `turns`, `final`, and `summary` in that order. `schema_version` is `1` and `game` is `tidefront-v1`.

Turns are chronological. Each turn object contains exactly `turn`, `utc`, `nodes`, `fleets`, `score_delta`, and `scores` in that order. `score_delta` is the ownership score earned on that turn, while `scores` is cumulative through that turn. Within every turn, nodes are sorted by node ID, fleets by fleet ID, and both score arrays by player ID. Final nodes, fleets, and scores use the same ordering. A fleet row records the order kind, target only for a move, final node for that turn, and one of `hold`, `moved`, `blocked-edge`, `blocked-depth`, `blocked-contest`, or `blocked-occupied`.

`summary.turn_count` equals the number of turns and `summary.fleet_count` equals the final fleet count. `summary.sha256` is lowercase SHA-256 over these UTF-8 records in turn order:

- `T<TAB>turn<TAB>utc<LF>`
- one `N<TAB>node_id<TAB>tide_m with six decimals<TAB>effective_depth_m with six decimals<TAB>owner<LF>` per sorted node
- one `F<TAB>fleet_id<TAB>node_id<TAB>status<LF>` per sorted fleet
- one `S<TAB>player_id<TAB>cumulative_points<LF>` per sorted score

The implementation must be deterministic across worker counts, working directories, input ordering, and repeated runs. Additional valid matches and tide inputs may be used during verification, so fixture-specific output is not acceptable.
