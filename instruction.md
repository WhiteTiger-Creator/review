A build tool resolves a stream of scenarios, one version per queried module.
`main.go` wires I/O and `make` builds `resolve` (stdin→stdout); complete
`resolveStream` in `select.go`. `docs/` fixes the row grammar and output
layout.

A module's answer is its selected version, `NONE` if it never joins the main
module's reachable set, or `CONFLICT` if reachable but over-constrained.

- **Floors, not pins.** A `LOCK` and any carried version are floors: they raise
  a selection, never cap it.
- **Session carry.** Scenarios share tables until a `RESET`. Each module's
  selected version becomes its floor in every later scenario; a module never
  built carries nothing.
- **Demand first.** Compute *demand* as the least fixed point of floors and
  requirement edges with every ceiling ignored. A requirement or ceiling
  declared by version U of a module applies only once that module's **demand**
  reaches U; the main module's always apply.
- **Then retract.** Demand alone decides conflict: a module whose demand exceeds
  its lowest in-force ceiling (a `CAP` or a scar) is over-constrained. Recompute
  the fixed point with those modules contributing no requirement edges, so
  modules reachable only through them are `NONE`. Ceilings are *not* re-derived
  from that second pass — a conflicted module's own `CAP` rows keep binding, and
  can themselves conflict a module reachable elsewhere.
- **Conflict scars.** A conflicted module lifts no floor; its binding ceiling is
  remembered session-wide, ratcheting only lower and re-imposed every later
  scenario until `RESET`, even absent a `CAP`. A carried floor above a scar keeps
  re-conflicting.
