A build tool resolves a stream of scenarios into a lock table: one selected
version per queried module. `docs/row-grammar.md` defines the input rows;
`docs/output-contract.md` the output. Complete `resolveStream` in `select.go`;
parsing and formatting are wired in `main.go`. `make` builds `resolve`, which
reads the stream from stdin, writing result lines to stdout.

Within a scenario a module's answer is the version a correct resolver settles
on, `NONE` if it never joins the set reachable from the main module, or
`CONFLICT` if it is reachable but over-constrained. Four rules interact:

- **Version-conditioned edges.** A requirement or ceiling attached to version U
  of a module applies only once that module's own selection reaches U. The main
  module's edges always apply.
- **Floors, not pins.** A `LOCK` entry, and any version carried in, are floors:
  each can raise a selection, never cap it. A floor at or below the otherwise
  selected version has no effect.
- **Session carry.** Scenarios share one lock table that only grows; the version
  selected for a module becomes its floor in every later scenario, until a
  `RESET` line clears the accumulated floors. A module never built carries
  nothing.
- **Ceilings and conflict.** A `CAP` bounds a module from above. Judge each
  module against the highest version any in-force requirement demands of it: if
  that demand exceeds its lowest in-force ceiling, the module is over-constrained
  (`CONFLICT`) and contributes no edges, so modules reachable only through it
  are `NONE`.

Resolving each scenario in isolation, or ignoring the ceilings, is incorrect.
