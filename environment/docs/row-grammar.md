# Input row grammar

Input arrives on standard input as one or more scenarios, processed in the
order they appear. Each scenario is a block delimited by a `SCENARIO <id>` line
and a matching `ENDSCENARIO` line. A `RESET` line may appear on its own between
scenarios (never inside a block); it marks a boundary described in the
instruction. Between the `SCENARIO`/`ENDSCENARIO` lines the following row kinds
may appear in any order:

- `ROOT <module>` names the main module of the scenario. Exactly one `ROOT`
  row appears per scenario.
- `REQ <module> <atversion> <dep> <version>` records that **version
  `<atversion>` of `module`** requires `dep` at `version`. Different versions of
  the same module may record different edges, so `<atversion>` labels which
  release of `module` declares the edge. A module may record several requirement
  edges, may appear as the `dep` of several modules at different versions, and
  may list itself. Requirement edges may form cycles. For the main module named
  by `ROOT`, the `<atversion>` label carries no weight: the main module's edges
  are always in force.
- `CAP <module> <atversion> <dep> <maxversion>` records that **version
  `<atversion>` of `module`** forbids `dep` from resolving above `maxversion`
  (an upper ceiling). It is gated exactly like a `REQ` edge: it applies only
  once `module` is built and its selection has reached `<atversion>` (the main
  module's caps always apply). A `dep` may carry ceilings from several modules;
  the binding ceiling is the lowest of them.
- `INDEX <module> <v1> <v2> ...` lists every version published for `module` in
  the registry, in ascending release order.
- `LOCK <module> <version>` is one entry of the incoming lock table, recording
  the version a previous resolution pinned for `module`.
- `QUERY <module>` asks for the version chosen for `module`.

Every module id mentioned in any row is an implicit module of the scenario. A
version is written with a leading `v` and three dot-separated decimal fields,
for example `v1.4.0` or `v12.3.10`, with no leading zeros in a field. All
tokens are ASCII with no embedded spaces and fields are separated by single
spaces. Some modules and some requirement edges belong to no path out of the
main module; they are present in the input but sit off to the side.
