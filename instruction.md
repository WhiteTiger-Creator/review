Need a bash adversarial evaluator for the tabular scoring API under `/app/environment`. Correct the implementation so each case flips the model decision under the published octet budget while staying schema-valid; editing only `/app/output` artifacts will not pass.

Drive the run with this command.

```
bash /app/environment/cli/hx_drv.sh --policy /app/environment/v1/caps_a.json --cases /app/environment/k2/demo --out /app/output/adv_report.json
```

That command must regenerate `/app/output/adv_report.json` and `/app/output/spend_trace.jsonl`. Hand-written or static JSON is not enough; after a wipe of `/app/output`, the same CLI rerun has to recreate both files. Policy caps (`octet_budget`, `seed`, `flip_target`) are in `/app/environment/v1/caps_a.json`. Report and trace field meanings, wiresize accounting, digest rules, and the seeded visitation order (sort by sha256 of `seed:basename`, not glob order) are in `/app/environment/v1/form_shape.md`. Digests there are sha256 truncated to 16 lowercase hex characters over the documented UTF-8 payloads (including the jq `-c -S` canonical form for `cand_digest`).

Each successful case must reach `flip_target` after the shipped defense preprocessing stage (that stage is part of the threat model), spend at most `octet_budget` of encoded wiresize, keep schema-valid records, and use that seeded visitation order for the published seed. Held-out cases under `/app/environment/k2/xtra/` must meet the same envelopes. Intermediate probes under `/app/output/probe/` are advisory only; terminal report convergence is required.
