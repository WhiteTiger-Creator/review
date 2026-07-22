The directory /app holds a small offline data-processing tool that turns prepaid gondola-schedule telemetry into a billing-style ledger report. It ingests two structured text files (a line-config and a usage-event stream) and replays the stream against the configured allocations to produce a deterministic ledger, one record per line on standard output.

Run it as:

    python3 /app/report.py <line-config> <boarding-stream>

Both arguments are paths to text files. The line-config declares gondola and line allocations (each with a threshold, an absolute limit, and a surge window in ticks, plus an optional line standby-pool capacity) and maps each gondola to one line. The usage stream carries timestamped BOARD and ALIGHT events. Every boarding event must satisfy both the gondola allocation and its line allocation; the most restrictive of the two decides, and each event is all-or-nothing. Caps are absolute; crossing the threshold opens a per-allocation surge window; a shortfall may be borrowed from the line's shared standby pool and later repaid by credits.

The provided `report.py` already parses and validates both input files, but its `build_ledger` step is only a placeholder: it echoes every BOARD as `BOARDED` and applies none of the allocation model. Your job is to complete `build_ledger` so the report matches the contract exactly.

The complete output contract is specified in /app/docs/spec.md: the allocation model, the surge-window lifecycle (inclusive expiry, cancel and restart), the standby-pool standby and return ordering, the exact output records and their canonical ordering (BOARDED, REJECT, SURGE_START, STANDBY, RETURN), and error handling. Implement the transformation to match that contract exactly. Malformed input, an unknown gondola, or any structural violation must write a diagnostic to standard error and exit with a nonzero status without printing a ledger.
