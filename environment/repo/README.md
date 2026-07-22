# dataplan-report

A small offline data-processing tool that turns prepaid gondola-schedule telemetry
into a billing-style ledger report. It ingests a timestamped stream of
data-usage and credit events together with per-gondola and per-line
threshold/limit allocations (with surge timers and a bounded shared family standby
pool) and emits a deterministic ledger of usage verdicts, surge-state
transitions, and standby-pool activity.

```
python3 report.py <line-config> <boarding-stream>
```

The required output covers the gondola-and-line conjunction, the threshold/limit
limits, the surge-window lifecycle, the inclusive surge boundary, the shared
line standby pool with standby/return debt, and the canonical ledger ordering. It is
described in [docs/spec.md](docs/spec.md). The report builder lives in
[report.py](report.py): the argument handling, file reading, parsing, and
printing are fixed, and only the `build_ledger` transformation needs to be
completed.
