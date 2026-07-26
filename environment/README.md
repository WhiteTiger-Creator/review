# Opaline Dungeon Route Cartographer

Opaline's dungeon level desk uses this library-only Go module `opaline/cartographer` at `/app/opaline` to study every shortest winning adventurer route through a compact puzzle dungeon with keys, doors, crumbling floors, and portals. It is a games level-analysis helper for designers, not a generic graph toolkit.

## Public API

`Analyze(board Board) Analysis` and `Validate(board Board, candidate Analysis) ValidationStatus` are defined in package `cartographer`. Types, field order, and constant order are fixed in the sources under `/app/opaline`.

Both functions are deterministic, side-effect-free, and safe for concurrent calls. They must not mutate caller-owned tile slices, touch the filesystem or environment, use randomness or clocks, print, spawn processes, or keep mutable globals. Returned slices and strings are freshly owned. Empty outputs use non-nil empty slices.

## Boards

Boards are row-major. Valid sizes are 2–8 rows and 2–8 columns with exactly `Rows*Cols` tiles, one start, and one exit. Ordinary floor, wall, start, exit, and crumble tiles use an empty tag. Key and door tags are one character from `a`–`d` (at most one key per tag). Portal tags use the same character range in a separate namespace and always appear in pairs.

## Observable state

A state is the occupied coordinate, the set of collected key tags, and the set of collapsed crumble coordinates. Keys persist. The start cell behaves as floor after initialization. Entering a key collects it before the next move. A door is enterable only when its key is already held. A crumble cell collapses only after the player leaves it through a successful move; illegal attempts do not collapse the current cell. Walls, collapsed cells, locked doors, and out-of-bounds cells cannot be entered.

## Movement and portals

Moves are orthogonal. Canonical order is Up, then Right, then Down, then Left. Entering a portal lands on its partner in the same move; the trace destination is the partner. Portal transfer does not chain. Landing on the exit ends the route immediately.

## Shortest routes and metrics

For a solvable board, report the minimum move distance, the exact count of distinct shortest winning move sequences as an unsigned decimal string without leading zeros (including values larger than sixty-four bits), the lexicographically smallest shortest sequence, and a full trace of that sequence. Each trace step carries indices from 1, from/to coordinates, sorted held keys, and sorted cumulative collapsed coordinates.

Mandatory landings list coordinates shared at the same step index by every shortest route. Decision points on the canonical route list every shortest-winning next move from that exact complete state, in canonical order, when two or more exist.

Unsolvable valid boards use distance `-1`, count `"0"`, and empty non-nil slices. Invalid boards and unfinished placeholder results use distance `0`, count `"0"`, and empty non-nil slices with their matching status. Never return partial routes.

`Validate` accepts only an exact match to the canonical solved or unsolvable analysis for valid input, and only the canonical invalid analysis for invalid input.

## Documentation and examples

See `/app/opaline/docs/dungeon-rules.md`, `/app/opaline/docs/shortest-routes.md`, and `/app/opaline/docs/route-metrics.md`. Example layouts live under `/app/opaline/examples` (`gallery.go`, `sunken_archive.go`, `mirror_passage.go`).
