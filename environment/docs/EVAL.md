# Held-out evaluation protocol (K7 witness metrics)

This task is **machine-learning model evaluation**, not a generic JSON or log transform pipeline. The agent repairs an **inference-reduction worker** so offline metrics match a sealed reference instrument on frozen captures.

## Evaluation arms

- **Canonical pack** `/app/environment/bundle/k7/base.k7` defines the primary inference batch.
- **Padded holdout** `/app/environment/bundle/k7/var089.pad` tests generalization when trailing filler bytes are present; stamps must agree with the instrument on the logical frame.
- **Eval shards** under `/app/environment/data/wt_pair/` supply held-out labels (`scope_expect`, epoch fields) bound to captures by name (including `NN-<capture>.json` prefixes).
- **Retry schedule** `/app/environment/data/retry_schedules.json` exercises idempotent transition replay (duplicate `transition_id` must not duplicate state).

## Metric contract

Top-level `metric_fold` is an eight-digit hex digest coupling sorted `L-*` inference rows (scope, anchor, instrument stamp), sorted `R-*` retry rows, and pack entry count. Recompute after every `emit`; see section 9 of `MODEL.contract`.

## Leakage and fairness

Do not replace the reference instrument, edit pack or shard bytes, or paste static report JSON. All graded formulas and binding rules are in `MODEL.contract`, `COLS.md`, and `FORMAT.contract`.

## Reference instrument

`/opt/k7probe/dy observe` returns `canon_hex` for each capture frame. Every `L-*` `rationale_text` must embed that stamp for the corresponding capture bytes.
