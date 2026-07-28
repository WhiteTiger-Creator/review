# Offline build-slice contract

The command is:

`go run /app/environment/cmd/slice --all-scenarios --write /app/output/buildslice_report.json`

It reads `/app/environment/vendor_tree/graph.json` and every `.json` file directly under `/app/environment/scenarios`. It writes the requested report plus `buildslice_cache.json` and `buildslice_run.json` in the same directory. Inputs are offline and all output is deterministic.

## Input model

`graph.json` is an object with exactly these logical fields:

- `schema_version`: integer `1`.
- `module`: string.
- `retired`: array of package import-path strings.
- `replaces`: array of objects with string fields `old` and `new`.
- `packages`: array of package objects.

A package object has:

- `import_path`: unique string.
- `tag_sets`: array of clauses. A clause is an array of tag terms. Clauses are OR alternatives and terms inside one clause are AND requirements. A positive term requires that tag; `!name` requires that `name` is not enabled. An empty clause is always active.
- `imports`: array of import objects. Each import has `path` (string), `optional` (boolean), and `priority` (integer). Required imports use `optional: false` and `priority: 0`. Optional imports use `optional: true`; their `priority` field means the integer contribution from 1 through 1000 added to the global option score when that edge is selected.

A scenario manifest has exactly `scenario_id` (non-empty string), `tags` (array of strings), `roots` (non-empty array of import paths), and `ceiling` (positive integer). Scenario IDs must be unique. A tag and its negation cannot both appear. Scenario tag order is preserved in output and digest input.

The bundled scenario IDs are `s01_base_docs`, `s02_base_cache`, `s03_base_global`, `s04_base_wide`, `s05_linux`, `s06_integration_tight`, `s07_integration_shared`, `s08_integration_wide`, `s09_explicit_negation`, `s10_cgo`, `s11_replace_chain`, and `s12_dual_roots`. Additional manifests may use any other valid non-empty ID.

## Activation and replacement

A retired package is never active. For every other package, at least one `tag_sets` clause must match the scenario tags. Imports whose resolved target is inactive are absent from that build variant.

Replacement resolution uses the longest matching `old` path where the import equals `old` or begins with `old/`. The unmatched suffix is appended to `new`. Resolution repeats until no mapping matches. Replacement cycles are invalid. Roots are resolved by the same rule.

Every root must resolve to an active package. Every active import target must exist after replacement. There may be at most 20 reachable optional imports in one scenario.

## Closure and optional selection

Required imports of a kept package are always followed. An optional import is followed only when that exact edge is selected. Its stable edge ID is `source_import_path->resolved_target_path`.

Among all valid selected-edge sets whose complete package closure is at most `ceiling`, choose one by these rules in order:

1. Maximize the sum of selected optional-import priorities.
2. If scores tie, maximize the number of kept packages.
3. If both tie, compare the sorted selected edge-ID arrays lexicographically and choose the smaller array.

A selected edge is valid only when its source is in the resulting closure. Shared dependencies count once. A selected optional package may expose further optional edges, which are independent decisions. The mandatory closure with no optional edges must fit the ceiling; otherwise the input is invalid.

## Scenario report object

The `schema_version` field identifies the exact JSON contract version for each artifact: report version 2 and cache/run-record version 1.

Each scenario object has exactly these fields and types:

- `scenario_id`: string.
- `tags`: array of strings, in manifest order.
- `roots`: array of strings, in manifest order.
- The `resolved_roots` field is defined as the sorted array of root paths after complete replacement resolution.
- `ceiling`: integer.
- `kept`: sorted array of active package paths in the selected closure.
- `dropped`: sorted array containing every graph package not in `kept`.
- The `drop_reasons` field means an object with exactly one reason entry for every path in `dropped`, using the precedence below.
- The `selected_options` field reports the sorted optional edges chosen by the optimizer; each object has exactly `from` (string), `to` (string), and `priority` (integer).
- The `option_score` field equals the integer sum of all priorities in `selected_options`.
- The `budget_used` field equals the integer number of package paths in `kept`.
- `roots_reachable`: boolean.
- `within_budget`: boolean.
- `input_digest`: 64-character lowercase SHA-256 hex.
- `plan_digest`: 64-character lowercase SHA-256 hex.

Drop reason precedence is exact: `retired` first, then `tag_excluded`, then `budget_trim` for an active package reachable when all optional edges are enabled but omitted by the selected budget plan, otherwise `unreachable`.

For valid scenarios, `roots_reachable` and `within_budget` are true. `dropped` and `kept` do not overlap.

## Digest bytes

Canonical input JSON means UTF-8 JSON with object keys sorted, arrays preserved, no insignificant whitespace, and a single JSON representation for numbers. `input_digest` uses the `sha256` algorithm (SHA-256) over:

`canonical_graph_json + "\n" + canonical_scenario_json`

For manual interoperability checks, the standard command `cksum -a sha256` may be fed the exact bytes above. This is only a diagnostic; tool choice is not part of the implementation contract.

The `plan_digest` field is computed as SHA-256 over the UTF-8 bytes of these newline-separated records, in this exact order:

- `scenario_id=<value>`
- `input_digest=<value>`
- `tags=<tags joined by ASCII unit separator 0x1f>`
- `roots=<roots joined by 0x1f>`
- `resolved_roots=<sorted roots joined by 0x1f>`
- `ceiling=<decimal>`
- `kept=<sorted paths joined by 0x1f>`
- one `drop=<path>:<reason>` record per dropped path, sorted by path
- one `option=<from>-><to>@<priority>` record per selected option, sorted by edge ID
- `option_score=<decimal>`
- `budget_used=<decimal>`
- `roots_reachable=<true|false>`
- `within_budget=<true|false>`

`summary.report_digest` is SHA-256 over sorted lines `scenario_id|input_digest|plan_digest`, joined by newline.

## Top-level report

The `summary` field reports the number of scenarios, whether every plan converged within its ceiling, and the digest binding all scenario plans.

`buildslice_report.json` has exactly:

- `schema_version`: integer `2`.
- `command`: the command string shown at the top of this document.
- `scenarios`: scenario objects sorted by `scenario_id`.
- `summary`: object with exactly `scenarios_total` (integer), `all_converged` (boolean), and `report_digest` (64-character lowercase hex).

The report must be byte-identical on unchanged reruns.

## Incremental cache and run record

The `entries` field is the cache index: an array sorted by `scenario_id`, with one item binding a scenario ID and input digest to its complete scenario plan. `buildslice_cache.json` has exactly `schema_version` integer `1` and `entries`. Each entry has exactly `scenario_id`, `input_digest`, and `plan`, where `plan` is the complete scenario report object. An entry is reused only when its input digest matches. Graph changes invalidate every entry; one manifest change invalidates only that scenario. Entries for removed manifests are deleted.

`buildslice_run.json` has exactly:

- `schema_version`: integer `1`.
- `reused`, `recomputed`, and `removed`: sorted arrays of scenario IDs.
- `cache_rebuilt`: boolean, true only when an existing cache was unreadable or incompatible and had to be discarded.
- `cache_digest`: SHA-256 over sorted cache lines `scenario_id|input_digest|plan_digest`, joined by newline.
- `report_digest`: the report summary digest.

A missing cache is a normal cold run and does not set `cache_rebuilt`. A malformed or incompatible cache is ignored, all current scenarios are recomputed, and `cache_rebuilt` is true. After one warm run, unchanged reruns make the report, cache, and run record byte-identical.

## Failure and write behavior

Malformed JSON, duplicate IDs or package paths, conflicting tags, invalid import metadata, missing resolved targets, replacement cycles, inactive roots, too many reachable optional edges, or a mandatory closure over the ceiling are invalid. The command exits nonzero and does not replace any existing report, cache, or run file. Successful writes use complete JSON documents ending with a newline.
