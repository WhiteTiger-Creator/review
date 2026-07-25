A build tool resolves a stream of scenarios, one version per queried module.
`main.go` wires I/O and `make` builds `resolve` (stdin→stdout); complete
`resolveStream` in `select.go`. `docs/` has the exact grammar. An `INDEX` row
lists a module's published versions; it is informational, never bounding
selection.

A module's answer is its selected version, `NONE` if it never joins the main
module's reachable set, or `CONFLICT` if reachable but over-constrained. Rules
interact:

- **Version-conditioned edges.** A requirement or ceiling on version U of a
  module applies only once its selection reaches U; the main module's edges
  always apply.
- **Floors, not pins.** A `LOCK` and any carried version are floors: each raises
  a selection, never caps it, inert at or below the otherwise selected version.
- **Session carry.** Scenarios share tables persisting until a `RESET`. Each
  module's selected version becomes its floor in every later scenario; a module
  never built carries nothing.
- **Ceilings and conflict.** A `CAP` bounds a module from above. Its lowest
  in-force ceiling is compared with the max of its floors and in-force
  requirement edges. Exceeding it makes the module over-constrained
  (`CONFLICT`), contributing no edges, so modules reachable only through it are
  `NONE`.
- **Conflict scars.** A conflicted module lifts no floor; its binding ceiling is
  remembered session-wide, ratcheting only lower and re-imposed every later
  scenario until `RESET`, even absent a `CAP`. A carried floor above a scar keeps
  re-conflicting.

Per scenario emit one line per queried module, ascending module order:
`<scenario-id>|<module>|<version>`, version verbatim (or `NONE`/`CONFLICT`);
nothing else.
