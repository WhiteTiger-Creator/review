# Emberline Hex Tactics

Library-only Java 21 simultaneous-turn tactics resolver for axial hex boards.

## Layout

- `src/main/java/dev/emberline/game/` — public immutable API
- `scenarios/` — three human-readable example setups
- `Makefile` — offline `javac --release 21` compile and JAR assembly

There is no public `main` class and no installed game executable. Call
`TurnResolver.resolve(Board, List<Order>)` from your own tooling.

## Axial hexes

Coordinates use axial `(q, r)`. Distance between two hexes is
`(abs(dq) + abs(dr) + abs(dq + dr)) / 2`. Adjacent hexes have distance 1.

The `terrain` map lists every playable hex. `WALL` cells are playable keys but
cannot hold units or be MOVE/ATTACK targets. Units may not start on walls.

## Units and orders

Unit IDs match `[A-Za-z0-9][A-Za-z0-9._-]*`, are unique, and occupy unique
non-wall playable hexes. Health is positive. Initiative, range, and power are
non-negative. Team scores are non-negative and strictly below a positive
`scoreToWin` at turn start.

Every unit must receive exactly one order:

- `HOLD` — target must be null
- `MOVE` — target must be an adjacent playable non-wall hex
- `ATTACK` — target must be a playable non-wall hex within the unit's range

Invalid boards or orders throw `IllegalArgumentException` before any effect.

## Simultaneous movement

Only `MOVE` orders create movement intents. When several movers target the same
hex, keep the contender with greatest initiative; break ties with the
bytewise-smallest unit ID. Rejected contenders stay put and emit `MOVE_BLOCKED`.

Resolve retained intents against initial occupancy. A retained mover succeeds
if the destination was initially empty, or if that occupant also has a retained
move that succeeds. Closed cycles (including swaps) succeed in full. A chain
that ends on a unit that holds, attacks, or lost contention fails in full, and
failure propagates backward. Independent components do not affect each other.
Successful movers emit `MOVE`; failed retained movers emit `MOVE_BLOCKED`.

## Combat, hazards, scoring

After movement, every unit that began the turn executes its `ATTACK` against the
post-move target hex. Hits require an opposing occupant; friendly and empty
targets miss. Damage equals attacker `power`. Attacks still resolve when the
attacker takes lethal damage in the same turn.

Accumulate attack damage simultaneously, then add one hazard damage for each
unit ending on `HAZARD`. Emit one `DAMAGE` event per damaged unit with the
combined amount, then remove units at zero or less health. Survivors keep
reduced health. Defeated units cannot score.

Each surviving unit on a `BEACON` scores one point for its team. If both teams
reach `scoreToWin`, status is `DRAW`; otherwise the reaching team wins; else
`ONGOING`.

## Event order

Events are grouped as: movement (by unit ID), attacks (by attacker ID), damage
(by unit ID), defeats (by unit ID), then scores (Amber units by ID, then Cobalt
units by ID). Resulting units are sorted by ID; terrain iteration is ordered by
`q` then `r`.

## Scenarios

See `scenarios/crossing-lines.txt`, `scenarios/beacon-race.txt`, and
`scenarios/hazard-ring.txt` for sample boards and order sketches. They document
setup only; they are not full resolved transcripts.

## Build

```bash
make        # compiles classes and builds build/emberline-game.jar
make clean  # removes build/
```
