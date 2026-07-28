Night shift blocked a mesh config promotion because the security posture reconciler at `/app/cmd/meshgate` is not producing a compliant `/app/output/posture.json`. The reconciler replays signed unit streams from `/app/data` against the mesh policy at `/app/spec/mesh_policy.json` and must report security posture per the normative contracts in `/app/spec/mesh_stream_protocol.md` and `/app/spec/posture_schema.md`.

Bring it into compliance with the security baseline. Treat both spec files as authoritative — every behavior the verifier checks must be derivable from them without reverse-engineering hidden reference logic.

## Required behaviors (summary)

**Output:** Write `/app/output/posture.json` with top-level fields `recoverable`, `gateways`, and `drift_events`. All list fields must serialize as JSON arrays (`[]`), never `null`.

**Stream processing:** Validate records in the priority order documented in `mesh_stream_protocol.md`. Signature payloads use `gateway_id|seq|ts|unit_id|op|metric|val|offset` with four-decimal float formatting for `val` and `offset`.

**Calibration:** `adjusted_val = raw_val + active_offset`. Each applied `TUNE` **replaces** the active offset (default `0.0`); offsets do not accumulate. Staged `TUNE` ops inside batches follow batch commit ordering — see the worked examples in `mesh_stream_protocol.md`.

**Batch transactions:** Stage `TELEMETRY` and `TUNE` while a batch is open; apply on `BATCH_COMMIT` in chronological order. Abort discards staged state.

**Recoverability:** Gateways with `invalid_seq`, `duplicate_seq`, or `bad_signature` are unrecoverable and omit unit output. When global `recoverable` is `false`, skip all policy evaluation.

**Policy drift:**
- `binding_breach` — evaluated **per gateway** for each bound pair; emit one policy-wide event (`gateway_id: ""`, `seq: 0`) per violating gateway, without deduplication. See the worked example in `posture_schema.md`.
- `site_forbidden` — active unit on a gateway outside its home-site list.
- `sync_skew` — cross-gateway reference-average delta strictly greater than `0.05` for a sync metric present on at least two gateways.

**Drift events:** Use the exact `reason` labels and `detail` string formats from `posture_schema.md`, including `bad_signature`, `binding_breach`, `site_forbidden`, and `sync_skew`.

Default paths are fine; keep support for `--data-root`/`--data`, `--policy`, and `--output`.
