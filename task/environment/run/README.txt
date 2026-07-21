Runtime state files for the simulator. The built driver is installed to /usr/local/bin/arena.

## CLI

```
arena --scenario <basic|stress|stress2> --profile <burst|steady> --order <a_then_b|b_then_a> --out <path> [--seed <n>]
```

Load profiles fire on every tick for the full scenario length, including ticks while the client is detached. Detach stops notification handoff to the live client, not submission ingestion.

Detach writes a journal stamp (u32 generation, u64 cursor — 12 bytes per stamp). The stress2 scenario performs two detach cycles.

## Report JSON

Path: `/app/output/report.json`

Top-level keys: `scenario` (string), `profile` (string), `events` (array).

Each event object has `kind` (`submit`, `complete`, or `notify`) and `id` (integer request id).
