Fix the simulator source under `/app/src` and headers under `/app/include` so `/usr/local/bin/arena` produces a correct `/app/output/report.json` under detach/reattach stress and differing internal reconciliation order. Output-only edits or hand-written JSON will not pass; the verifier rebuilds with `make -C /app`, reruns the driver across multiple scenario, profile, and order combinations, and grades with `pytest` on `/tests/test_outputs.py`. Unknown scenario, profile, or order flags (for example `z_then_y`) must be rejected by the CLI.

Under load the completion ring breaks delivery guarantees: duplicate or missing completions, and notifications that do not match completions.

Start in the tick-driven simulator pipeline under `/app/src` (ingest, settle, merge, link, journal I/O). Reports use top-level `scenario`, `profile`, and an `events` array. Each event records `kind` (`submit`, `complete`, or `notify`) and integer `id`. Load profiles fire on every tick for the full scenario length, including ticks while the client is detached. Detach appends a 12-byte journal stamp (u32 generation, u64 cursor); the stress2 scenario performs two detach cycles (24 bytes of stamps minimum on disk).

Correctness invariants:

- Each submit introduces a new request id (no reuse within a run). Ids start at 1 and are contiguous through the final id for that run; submit events appear in log order as 1..N.
- Every submitted id is completed exactly once; every completion has exactly one notify for the same id. The log has three events per submit and at most one row per `(kind, id)`.
- In the event log, submit precedes complete and complete precedes notify for each id; walking left to right, no notify before complete and no complete before submit for any id.
- Tick-driven simulation: completions must not all appear in one terminal dump; the log should show work spread across the run with submits and completes interleaved across ids.
- Reconciliation order (`a_then_b` vs `b_then_a`) must keep the same id coverage on burst stress runs but change the emitted sequence.
- Identical flags on rerun must yield the same sequence; different scenario or profile choices must not reuse one canned sequence.

Invalid invocations must exit with failure and must not leave a report file at the requested output path. Grading uses `pytest` on `/tests/test_outputs.py` (harness flags such as --ctrf are allowed).
