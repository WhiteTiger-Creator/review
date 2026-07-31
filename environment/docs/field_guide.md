# Brief field contract

Required stage journal paths are `/app/output/stage/lane_warm.txt` and `/app/output/stage/lane_stress.txt`.

The graded artifact is `/app/output/proof_certificate_bundle.tar.json`. Use the independent replay verifier below.

```bash
/app/environment/tooling/verify_ob9_d9.sh --from /app/output/proof_certificate_bundle.tar.json
```

Stage summaries under `/app/output/stage` are diagnostic only. Terminal proof requires the bundle plus replay tool success.

Corpus playbooks under `/app/environment/corpus/playbooks/` and `/app/environment/docs/r5_link_notes.md` are operator chatter only. When they disagree with this guide or `/app/environment/schemas/contract_annex.yaml`, the annex and this guide win.

## Required top-level fields

- `arm_id` must be `0763`.
- `replay_digest` is an eight-character lowercase hex string binding row material and the live stain-bank fingerprint.
- `bank_fingerprint` is an eight-character lowercase hex string published from the stain bank after the stress epoch is active.
- `rows` is a list of scored duty records.
- `obligation_violations` is a non-negative integer counting closed-algebra breaches for catalog item nine.

## Stain bank

The HS driver must fold stain margins from `/app/environment/s4d` before cross terms. Limits `od_bias`, `bank_epoch_warm`, and `bank_epoch_stress` live in `/app/environment/k8m/lim_a763.toml`. Cache entries are namespaced by instance key, corpus tag, and bank epoch. Stress evaluation must not reuse warm-epoch cache hits. Margin algebra and fingerprint materialization are defined in `/app/environment/schemas/contract_annex.yaml`. On recovery reruns, clear `/app/output/stage/bank_cache.txt` together with lane journals before calling `run_hs_cycle.sh`.

## Row material

Each row carries `row_seq`, `instance_key`, `duty_cycles`, `corpus_tag`, and `lane_phase`.

Rows must be canonically ordered by `(instance_key, corpus_tag)` ascending, with contiguous `row_seq` starting at 1. The `corpus_tag` field is `a` or `b`. `lane_phase` must be at least 2 on the stress pass.

`replay_digest` is exactly 8 lowercase hex characters over sorted material joining `row_seq`, `instance_key`, `duty_cycles`, `corpus_tag`, and `lane_phase` with pipe separators and semicolon row suffixes in `row_seq` order, then the suffix `#bf|{bank_fingerprint}`, SHA-256, first 8 hex characters lowercase. The canonical Python row materializer is `/app/environment/tooling/digest_util.py` (`row_material_digest`).

## KIDX corpora

Corpora live at `/app/environment/k8m/corpus_*.kidx`. For tags at or above `reloc_base`, remap before formatting keys using reloc constants in `ref_a763.kaitai` including the annex `reloc_xor` fold loaded by the reloc helper, then format `instance_key` as lowercase `i` plus four hex digits. Per-entry `duty_cycles` uses the annex payload averaging spec in `/app/environment/schemas/contract_annex.yaml`, then adds the stain margin for the active bank epoch.

## Cross-triple duty aggregation and held-out salt

After stain-margin fold and base duty extraction, apply cross terms from `/app/environment/k8m/pair_v7.json` before digesting. The `instance_pairs` field lists each closed-algebra tuple with `key_a`, `key_b`, and `cross_weight`. Let `profile_word` and `holdout_salt` load from `/app/environment/k8m/lim_a763.toml` and `profile_mask` from the algebra file. Effective cross weight uses the annex masked xor blend that folds `holdout_salt` (not additive blending). For each pair, let `duty_a` be the `a` corpus row for `key_a` and `duty_b` the `b` corpus row for `key_b`. Corpus `a` `duty_cycles` becomes the annex cross product once both rows exist.

The driver publishes a calibration snapshot before the audit pass. Audit material must not reuse calibration corpus `a` duties when the profile stamp matches; audit corpus `a` rows must exceed their calibration base weights after cross terms and stress scaling.

Cross terms apply first. When `lane_phase` is at least 2, multiply corpus `a` `duty_cycles` by `stress_multiplier` from the same algebra file after cross terms. After scaling, each stress corpus `a` row must satisfy the annex stress floor against its paired corpus `b` row.

## Obligation nine counter

Recompute violations from final rows and `pair_v7.json` using tolerance from `/app/environment/k8m/lim_a763.toml`. For each pair, undo stress scaling when `lane_phase >= 2`, then derive expected duty from annex obligation-nine definitions that use the same masked cross (including `holdout_salt`), and reapply the scale. Count a violation when either row is missing, the scaled duty is not divisible by the scale, or `abs(duty_cycles - expected)` exceeds tolerance. The brief `obligation_violations` must equal the recomputed count. Stress arm must report zero violations.

`g09_chk.sh` must recompute this count from row material; it may not accept the JSON bundle document counter without verification.

## Stage journals

Journals are `/app/output/stage/lane_warm.txt` and `/app/output/stage/lane_stress.txt`. Line layout is documented in `/app/environment/logging/stage_format.txt`. Each line lists pass, lane, witness_seq, rows, duty_checksum, and status tokens separated by spaces. The `lane` field is the numeric publish lane token. The `pass` field is `warm` or `stress`. The journal `status` field records the pass digest token and must not substitute for bundle `replay_digest` row-material binding.

Warm `duty_checksum` binds pre-cross calibration rows after warm-epoch stain margins. Stress `duty_checksum` binds post-fold final bundle rows. Both use eight lowercase hex characters over sorted instance_key, corpus_tag, and duty_cycles tuples per annex journal definitions. Replay checks that stress `witness_seq` exceeds warm `witness_seq`, stress `lane` is at least 2, stress `rows` equals final row count, and stress `duty_checksum` matches the brief row material. Replay must not delete journals before reading them.

## Recovery semantics

If replay fails after a partial handoff, clear stale lane journals and `/app/output/stage/bank_cache.txt` before rerunning `/app/environment/exec/run_hs_cycle.sh --arm 0763 --all-fixtures`. Replay is idempotent on a valid brief.
