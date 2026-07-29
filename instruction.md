The K7 **model evaluation** desk under `/app/environment` runs **offline inference** over frozen enrollment captures, scores each capture against published **held-out eval shards** in `/app/environment/data/wt_pair/`, and must match the sealed reference **scoring instrument** at `/opt/k7probe/dy` on every evaluation arm. The Go **inference-reduction** worker currently emits `/app/output/k7_witness_report.json` with wrong scope labels, timing anchors, instrument stamps, or top-level `metric_fold` on padded holdout lanes, stacked alternates, relabeled shards, and repeated transition deliveries. Repair **model-evaluation semantics** in the worker and regenerate metrics through the published eval pipeline; static or hand-written JSON is insufficient.

## Deliverable

- Output: `/app/output/k7_witness_report.json` — evaluation report with `lines` (each row: `line_id`, `scope_code`, `timing_anchor`, `transition_id`, `rationale_text`) and held-out **metric_fold** per `/app/environment/docs/MODEL.contract` and `/app/environment/docs/EVAL.md`.
- Build: `make -C /app/environment build` produces `/app/environment/bin/w7`.
- Pipeline: `/app/environment/tools/check-k7.sh`, then `w7 emit --out /app/output/k7_witness_report.json` (see `/app/environment/README.md`).

## Authoritative contracts

| Doc | Role |
|-----|------|
| `/app/environment/docs/EVAL.md` | Held-out eval protocol, metric_fold, leakage and instrument coupling |
| `/app/environment/docs/MODEL.contract` | Inference reduction, eval shard binding, retry idempotency |
| `/app/environment/docs/FORMAT.contract` | Wire-level emit shape |
| `/app/environment/docs/COLS.md` | Report column semantics and timing anchor reduction |
| `/app/environment/docs/WIRE.md` | Frame TLV notes (draft paragraphs may be stale) |
| `/app/environment/bundle/k7/README.txt` | Capture pack layout and probe usage |

`/app/environment/docs/EVAL_SHORTCUTS.md` and superseded draft notes in `WIRE.md` are **non-authoritative** decoys.

## Scope

Do not replace `/opt/k7probe/dy`, mutate bytes under `/app/environment/bundle/k7/` or `/app/environment/data/`, or satisfy the task by editing JSON at the output path. Held-out padded lane `var089.pad` and canonical pack `base.k7` stay byte-identical. **Generalization** must hold when capture packs, eval shard filenames, or retry schedules change under the same contracts.
