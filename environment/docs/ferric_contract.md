# Ferric contract

Shared vocabulary for this machine-learning HPO toolkit and its training-run archaeology path.
Companion machine-readable snippets live in `digest_concat_templates.json`.

## Trace rows

JSONL under `data/runs/`. Each row has

- `rid` string identity for the row
- `aid` string identity for the candidate configuration
- `step` non-negative integer step index
- `eta` floating learning-rate value observed at that step
- `vis` floating visible score (may be truncated or suppressed)
- `halt` early-stop tag string
- `nest` nest lineage token
- `lr0` floating base learning rate for that configuration
- `gamma` floating multiplicative decay
- `period` positive integer rung period

Load every `*.jsonl` under `data/runs/` except treat `side_bag.jsonl` as the sidecar bag, not as a primary trace batch.

## Sidecar bag

`data/runs/side_bag.jsonl` rows

- `rid` joins to a trace row
- `true_vis` the recovered score when the visible value was suppressed
- `hid` integer; when equal to 1, replace `vis` with `true_vis` for that `rid`

When `hid` is not 1, keep the trace `vis`.

## Early-stop tags

Normalize `halt` case-insensitively.

Treat these as halted - `e`, `cut`, `halted`.

Treat these as not halted - empty string, `ok`, `done`.

Any other tag is not halted.

A configuration is fully halted when its last step (highest `step` among its outer-lineage rows) is halted.

## Nestmap

`data/nests/nest_map.json` maps each `nest` token to an object with `outer` and `inner` string ids. Exact object shape is in `digest_concat_templates.json` under `nestmap_object_shape`.

Outer lineage means - for a configuration `aid`, keep only rows whose nestmap `outer` equals the mode outer among that aid's rows (ties break by lexicographically smallest outer id).

Inner ids are recorded on the ledger but must not contribute scores to rung totals.

Held-out nest cases live in `data/nests/nest_hold.json` with the same shape; the verifier may swap the active nestmap.

## Learning-rate rung semantics

For a configuration with `lr0`, `gamma`, `period`, the expected eta at a step is described by `eta_expected` in `digest_concat_templates.json`.

Integer division truncates toward zero. Observed `eta` must match that expected value within absolute tolerance `1e-9` for every kept outer-lineage row. Configurations that violate this are invalid and must not appear in `rung_sheet.arms`.

A rung boundary is any kept outer-lineage row where `step` modulo `period` is zero.

`rung_total` for a configuration is the sum of recovered scores on its rung boundaries.

`best_aid` is the valid, not-fully-halted configuration with the largest `rung_total`. Ties break by lexicographically smallest `aid`.

Grid files under `data/grids/` list candidate `(lr0, gamma, period)` triples. Public grid is `grid_pub.json`. Held-out grids are used by the verifier only.

When binding, each configuration's `(lr0, gamma, period)` must equal the unique grid triple that matches all of its outer-lineage rows. If rows disagree, the configuration is invalid.

## Holdout forge bag

`data/bags/forge_bag.json` carries bag_id (string), knob (unsigned 64-bit integer), and salt (string). Companion object shape also sits in `digest_concat_templates.json` under `forge_bag_shape`.

Forge score for the chosen `best_aid` with its bound `(lr0, gamma, period)`

1. Build the UTF-8 string using the `forge_string` template in `digest_concat_templates.json`, where `nest_outer` is the mode outer id used for that configuration.
2. Compute SHA-256 over that string.
3. Take the first 8 bytes as a big-endian `u64`, then divide by `(1<<64)-1` yielding an IEEE float on `[0, 1]`.

Twin runs with identical inputs must emit identical `sheet_digest`, `ledger_digest`, and forge score.

Absolute float tolerance for score comparisons is `1e-9`. Digests compare exact hex lowercase.

## Digests

`sheet_digest` is SHA-256 hex over UTF-8 concatenation of `sheet_line` templates from `digest_concat_templates.json` for each arm in ascending `aid` order. Arm object key order for human reading is `aid`, `rung_total`, `lr0`, `gamma`, `period`, `nest_outer`. See `float_format_note` in that JSON file for float rendering.

`ledger_digest` is SHA-256 hex over UTF-8 concatenation of `ledger_line` templates for cases sorted by `rid`, where `side` is 1 when score came from sidecar.

## Emit paths

Write `/app/emit/rung_sheet.json` and `/app/emit/align_ledger.json`. Create `/app/emit` if needed.

## Verifier hash primitive

Independent recomputation of sheet_digest and ledger_digest uses SHA-256 over the same UTF-8 concatenations. Python hashlib.sha256 is an allowed verifier primitive for that recomputation.
