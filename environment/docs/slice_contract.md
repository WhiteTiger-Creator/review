# Buildslice contract

Report path — `/app/output/buildslice_report.json`
Schema version — 1

## Top-level fields

- `schema_version` field is set to integer 1
- `command` field echoes the verifier command string
- `scenarios` array holds one object per manifest
- `summary.scenarios_total` counts bundled scenario entries
- `summary.all_converged` is a boolean field that reports when every scenario satisfies reachability and budget
- `summary.report_digest` is computed from scenario plan digests

## Scenario manifests

Twelve JSON manifests under `/app/environment/scenarios/` drive the planner. The `scenario_id` field set to `s01_base`, `s02_linux`, `s03_integration`, `s04_linux_plain`, `s05_shim_root`, and `s06_tight_base`. The same field set to `s07_core_only`, `s08_dual_int`, `s09_linux_tight`, `s10_wide_int`, `s11_optional_trim`, and `s12_replace_walk`. Suffix tokens such as `optional_trim`, `core_only`, `dual_int`, `replace_walk`, `wide_int`, and `linux_tight` are part of those basename values when naming focused scenarios. Each manifest lists `tags`, `roots`, and `ceiling`.

## Module graph (`vendor_tree/graph.json`)

The graph object lists `packages` (each with `import_path`, `imports`, `tag_sets`, and optional `optional`), `replaces` entries with `old` and `new` module paths, and a `retired` path list mirrored in `retired.txt`.

Each `import_path` names a Go package path used in kept and dropped report lists and in scenario root declarations.

## Scenario object fields

- `tags`, `ceiling` echo manifest inputs
- `kept`, `dropped` are sorted import paths; kept and dropped sets must not overlap
- `drop_reasons` maps each dropped path to a reason enum
- `budget_used` equals the kept package count
- `roots_reachable` is a boolean field that reports when declared roots stay reachable through kept imports
- `within_budget` is a boolean field that reports when kept count is at most the ceiling
- `plan_digest` is computed as described below

## Drop reason enums

- `tag_excluded` when a package is inactive under scenario tags
- `budget_trim` when removed to satisfy the ceiling
- `retired` when listed in retired.txt
- `unreachable` when not on any path from roots through active imports

## Digest reduction

See module comment in `cmd/slice/main.go` for `plan_digest` and `report_digest`. Each digest is a 16-character lowercase hexadecimal string.

## Convergence flags

When every scenario satisfies tags, ceilings, and reachability, each scenario reports `roots_reachable` true and `within_budget` true, and `summary.all_converged` is true.
