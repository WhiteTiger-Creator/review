Release forge emit under `/app/environment` writes `/app/output/forge_emit.json` and `/app/output/forge_checkpoint.json`, but resumed lane units drift from manifest byte counts, slot weights, and sealed digests after warm passes. Carry continuity breaks across chained invocations, partial lane requests drop unrelated checkpoints, and persisted lane fingerprints disagree with recomputation from the bundled manifest. Repair the implementation under `/app/environment` and regenerate outputs through the normal build pipeline.

Run `cmake -S /app/environment -B /app/build -G Ninja`, `ninja -C /app/build`, then `/app/build/forge_emit /app/environment/fixtures/lane.json /app/output/forge_emit.json <units>`. argv 1 is the manifest JSON path, argv 2 is the output JSON path, and argv 3 is a comma-separated unit list with no spaces. Lane units are `u_kappa`, `u_alpha`, and `u_zeta`. Tests delete generated outputs before each case and rerun the compiled binary, so static or hand-written JSON is insufficient.

## Output schema

The emit JSON object has exactly top-level keys "schema_version", "release_id", "order_weight_base", "pass_epoch", "units", "total_drift_bytes", "order_score", and "digest". "schema_version" is 1. "release_id" and "order_weight_base" are copied from the manifest. "pass_epoch" is the zero-based invocation counter read from checkpoint state before processing the requested units. The "units" array length equals the number of names in argv 3, in that request order. Each unit object contains exactly "name", "mode", "pass_index", "manifest_bytes", "record_bytes", "drift_bytes", "order_rank", "order_weight", and "row_digest". Resolved per-unit mode in the emitted JSON must follow manifest mode semantics for resume-capable units; do not branch on unit-name prefixes.

## Unit metrics

Each unit record file is line-oriented text. The parser reads the first line containing `size_bytes=` and extracts the integer byte count after the equals sign as "record_bytes". "manifest_bytes" is copied from the manifest entry. "drift_bytes" equals `record_bytes - manifest_bytes` as a signed integer. "order_rank" is the zero-based index of the unit within the manifest "units" array.

Manifest units declare a mode and start_pass. Fresh-path units compute `order_weight = order_weight_base * (order_rank + 1) + record_bytes` and `pass_index = start_pass`. Resume-path units with valid matching checkpoint state use `pass_index = next_pass` from that checkpoint entry and `order_weight = carry_weight + order_weight_base + record_bytes`, where carry_weight is the stored checkpoint value from the prior emission for that unit.

Aggregates over the requested units in the current invocation:
- "total_drift_bytes" is the sum of absolute drift_bytes across those units.
- "order_score" is the sum of order_weight across those units.

## Persisted lane checkpoint

The companion file `/app/output/forge_checkpoint.json` uses schema version 1, a lowercase 16-character "lane_token", integer "pass_epoch", and a "units" array sorted alphabetically by unit name containing only resume-mode units. Each entry records "name", "next_pass", "carry_weight", and "carry_drift". After each resume unit emission, "next_pass" equals `pass_index + 1`, "carry_weight" equals the emitted order_weight, and "carry_drift" equals the emitted drift_bytes. The lane token applies the digest accumulator below to newline-joined descriptor lines sorted alphabetically by unit name; the digest input includes one descriptor line for every unit declared in the manifest JSON. Each descriptor line is `name|mode|record|manifest_bytes|start_pass`.

Valid checkpoint state is read before generating resume units. Stale, corrupt, or lane-mismatched checkpoint files are ignored and resume units restart at their configured start_pass. When the on-disk lane token matches the active manifest, previously stored resume checkpoints must remain present after a partial invocation that updates only a subset of resume units. Units declared with fresh-start semantics ignore advanced resume checkpoint data and always recompute from their manifest start_pass.

Emit outputs are byte-stable only when the manifest JSON, requested unit list, and any on-disk valid checkpoint are all unchanged between invocations. A later invocation that reads advanced valid checkpoint state for a resume-capable unit must change that unit's pass_index and order_weight relative to a fresh-start emission.

## Digest algorithm

"digest" and "row_digest" are lowercase 16-character hex strings from the same byte-wise accumulator: start with 1469598103934665603, XOR each input byte, multiply by 1099511628211, and keep the low 64 bits at each byte step. All serialized metric fields in digest input use plain decimal integer formatting without leading zeros or decimal points.

Digest serialization uses pipe-separated field values only — never JSON key names. Lines are newline-separated.

Top-level digest input:
- First line: schema version, release id, order weight base, pass epoch, total drift bytes, order score — all pipe-joined.
- Remaining lines: one unit row serialization per emitted unit, in request order.

Unit row serialization (single line, values only, in this order):
`name|manifest_bytes|record_bytes|drift_bytes|order_rank|order_weight`

Do not hand-write output files or bypass the compiled entrypoint.
