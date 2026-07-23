# Evaluation book

Seed: **42**.

## Calendar partition

`train_end_slot` must be strictly less than `eval_start_slot`.

`temporal_leak_probe = 1` if any evaluation slot's `day` is less than or equal to any training slot's `day`, else `0`. Training slots are those with `id` in `[xSlot, train_end_slot]`; evaluation slots have `id >= eval_start_slot`. Do not infer leak cleanliness from `train_end_slot >= eval_start_slot` on slot id alone when `day` differs from `id`.

Board-ready packs need `temporal_leak_probe = 0` with gap >= 1.

## Prior shift signal

Sort logits `z` ascending. Split into `kParts` (>= 2) equal-count bins; remainder goes to the last bin.

`prior_delta = |mean(last_bin) - mean(first_bin)| / (1 + abs(mean(z)))`.

Surfaces shift when `prior_delta >= 0.12`.

Robust residual: project z onto covariate c, filter outliers beyond 2.0 standard deviations of initial residuals, refit on inliers (minimum 3), else use first-pass residuals. `prior_delta_residual` applies the prior_delta formula to the robust residual vector. Require `>= 0.08` when claiming shift is not covariate-buried.

## Accuracy gauge

`pred(x) = 1` if `x >= 0` else `0`. Labels from true logits use the same rule.

Adversarial margin perturbation: K = nSalt % 3; flip predictions on the K smallest-margin samples (ascending |logit|, index tie-break). Emit `acc_home`, `acc_shift`, and `acc_gap = acc_home - acc_shift`.

When `prior_delta >= 0.12`, require `acc_gap >= 0.05`.

## Digest-keyed memo

Metrics cache is keyed by pack_digest. Alternate or held-out digests must not inherit another digest's cached metrics within the same process.

## Seal event tape

`/app/output/stage_tape.jsonl` holds JSON lines with `pack_digest`, `tag`, `seal`, `parts`. Replay filters by pack_digest, maps tag to seal in file order, requires cal/prio/gauge/brief. Used for ledger recovery when checkpoint is missing.

## Board ledger chain

`pack_digest` = sha256 of `{ckpt}|{seed}|{nSalt}|{kParts}|{xSlot}|{span}`.

Stage seals: `cal`, `prio`, `gauge`, `brief` as in ops_notes.rst.

`ledger_chain` = sha256 of `{pack_digest}|{cal}|{prio}|{gauge}|{brief}`.

`resume_stamp` = sha256 of `{ledger_chain}|4`.

`tape_seal_count` = 4.

## Run repro stamp

`repro_digest` is the sha256 hex digest of the UTF-8 string:

`{seed}|{train_end_slot}|{eval_start_slot}|{temporal_leak_probe}|{prior_delta:.6f}|{prior_delta_residual:.6f}|{acc_home:.6f}|{acc_shift:.6f}|{acc_gap:.6f}|{nSalt}|{pack_digest}|{ledger_chain}`

with `seed = 42` and `nSalt` from the pack (board_q3 uses 7).

## scenario_score.json

Required fields:

- `seed`
- `partition_policy` (`"strict_calendar_gap"`)
- `temporal_leak_probe`
- `train_end_slot`
- `eval_start_slot`
- `prior_delta`
- `prior_delta_residual`
- `acc_home`
- `acc_shift`
- `acc_gap`
- `checkpoint_stamp`
- `pack_digest`
- `ledger_chain`
- `resume_stamp`
- `stage_seals`
- `repro_digest`
- `scoring_table` (object with the same numeric keys)
- `tape_seal_count` (integer 4)
- `held_out` (object with `prior_delta`, `prior_delta_residual`, `temporal_leak_probe` for the held_out pack)

## desk_ledger.json

Must restate `pack_digest`, `ledger_chain`, `resume_stamp`, and `stage_seals` matching `scenario_score.json`.

## uncertainty_brief.md

Markdown pipe tables for scoring questions. Numeric values must match `scenario_score` / `scoring_table` to 6 decimal places for floats. Rows sorted by key length ascending, then alphabetically. No triple-backtick fences. No executable snippets.

## Scoring questions

Tables should cover at least:

| question | value |
| --- | --- |
| temporal_leak_probe | (integer) |
| prior_delta | (float 6dp) |
| prior_delta_residual | (float 6dp) |
| acc_home | (float 6dp) |
| acc_shift | (float 6dp) |
| acc_gap | (float 6dp) |
| train_end_slot | (integer) |
| eval_start_slot | (integer) |
