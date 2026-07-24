# Lockfile Semver Range Inference

The offline lockfile tool under `/app/environment` is drifting in CI due to bugs in the source code.

Your task is to **debug and repair the broken Go source files** in `/app/environment` so that the tool behaves exactly according to the semantic rules verified by the tests.

## Overall Workflow

1. **Repair:** Edit the Go source files in `/app/environment` to fix the implementation.
2. **Rebuild:** Rebuild `/app/bin/depctrl` from `/app/environment` after edits, using the build recipe in `/app/environment/docs/phase_contract.md`.
3. **Execute:** Run `/app/bin/depctrl reconcile --all-mirrors` to verify. The automated tests will rebuild the binary and execute that path, or specific CLI chains.
4. **Verify:** Ensure the sealed output in `/app/output/constraint_report.json` meets all requirements.

## Test Requirements & Behaviors

The automated tests verify several critical behaviors. You must ensure your fixes correctly implement all of these:

- **Output Format & Overwrites:** The terminal report (`/app/output/constraint_report.json`) must be a JSON object with a `rows` array. Staging output is not the sealed report. Existing report files must be overwritten on a successful seal.
- **Digest Construction:** Each row needs `pkg`, `dep`, `lo`, `hi`, `pre_tok`, `lift`, and `row_digest`. `row_digest` must be the first 16 hex characters of the SHA-256 hash of the payload string `{pkg}|{dep}|{lo}|{hi}|{pre_tok}|{lift}` with `lift` formatted as `1` or `0`.
- **Peer Ceiling Semantics:** When `lift` is `true`, the resolved `hi` bound is capped by `peer_hi`. Raising `peer_hi` above the intersection loosens the ceiling.
- **Pre-Token Folding:** Arm tag `a` treats an empty `pre_tok` as `allow`. Arm tag `b` strips `-pre.` from bounds if `pre_tok` is not `allow`. An empty final `pre_tok` means bounds must not retain `-pre.`.
- **Sequence Logic:** Within a single arm tag, only the event with the highest `seq` number for a `(pkg, dep)` pair is kept for sealing.
- **Activation Gating:** Optional edges (e.g., `side-b`) appear only if their activation key is enabled in `/app/environment/data/act_map.json`. Disabling an activation key must immediately drop the edge, even if the cache is warm.
- **WAL CRC Handling:** The journal (`lock.wal`) must seal without torn or CRC-mismatched frames in the fold. Such invalid frames must be dropped and must not poison the output.
- **Cache Invalidation:** Warm cache blobs must stay coherent with the live peer fingerprint, activation map, and seeds. Stale ceilings (e.g., mutated `peer_hi`) must be correctly recalculated instead of hitting the cache.
- **CLI Chain:** The manual CLI chain of `depctrl collect` -> `depctrl reconcile` (without flags) -> `depctrl emit` must successfully seal a full terminal report.
- **Idempotency:** A double reconcile (running reconcile twice with identical inputs) must be completely idempotent, yielding the exact same generated digests and bounds.
- **Traces:** After a successful run, `/app/output/traces/last_run.json` must record `row_n` (number of rows in the sealed report), `frame_n` (where `frame_n >= row_n`), and `cache_hit`.

*Note:* `depctrl status` printing `steady` is not proof that the terminal report is correctly sealed. Hand-written reports or static mock outputs will fail.

See `/app/environment/docs/phase_contract.md` for specific technical recipes and cache constraints.
