Held-out **machine-learning evaluation** packs instrument captures under `/app/environment/bundle/k7/`. Eval shard JSON under `/app/environment/data/wt_pair/` supplies held-out label fields (`scope_expect`, `ds_inception`, `cert_not_before`) for the `timing_anchor` reduction in `/app/environment/docs/COLS.md`. Retry schedules in `/app/environment/data/retry_schedules.json` define idempotent transition keys for eval replay.

The reference scoring instrument at `/opt/k7probe/dy` defines canonical stamps for normalized frames. The **inference-reduction** worker must emit `/app/output/k7_witness_report.json` whose `lines` agree with that instrument and the eval shards on every capture, including padded holdout `var089.pad`.

See `/app/environment/docs/EVAL.md` for the held-out protocol. Certify metrics with `w7 emit` after recompiling the worker. The report must include top-level `metric_fold` (section 9 of `MODEL.contract`).
