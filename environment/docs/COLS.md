# Output columns (numerical witness schema)

The file `/app/output/k7_witness_report.json` is a JSON object whose `lines` field is an array with one object per bundled capture. Each row `line_id` field names that capture in witness tables. The `rationale_text` field must be non-empty and may include canonical stamp material from the reference instrument.

- `line_id` (string)
- `scope_code` (string)
- `timing_anchor` (integer Unix seconds)
- `transition_id` (string)
- `rationale_text` (string, non-empty)

## Timing anchor

For witness-driven rows, `timing_anchor` is the smaller of the witness integers `ds_inception` and `cert_not_before`:

`timing_anchor = min(ds_inception, cert_not_before)`

Draft note (superseded in `MODEL.contract`): some older notes used `max(ds_inception, cert_not_before)`; the evaluation contract uses the minimum.

## Witness directory wt_pair

The witness subdirectory name `wt_pair` holds JSON sidecar files under `/app/environment/data/wt_pair/`. Read every `*.json` file from that directory when building pack rows.

When a filename matches `<decimal-order>-<capture>.json`, the witness JSON applies to the pack entry whose capture name is exactly `<capture>` (for example `40-gamma-alt.json` binds to capture `gamma-alt`, not to the fourth sorted capture by position alone).

When a filename is a single stem without a numeric prefix (for example `a.json`), sidecars align with pack captures by lexicographic capture order: the first sorted sidecar file pairs with the first sorted capture name, and so on.

Each witness object includes `ds_inception`, `cert_not_before`, and `scope_expect` (string label that must match `scope_code` on the corresponding `L-*` report line).

## Idempotency

When the same frame delivery is retried with identical bytes and epoch, the pipeline must not emit a second row with the same transition identity. Retry deliveries are listed in `/app/environment/data/retry_schedules.json` under `steps`; each step includes `transition_id` matching the report row `transition_id` field.
