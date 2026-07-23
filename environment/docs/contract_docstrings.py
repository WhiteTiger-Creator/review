# -*- coding: utf-8 -*-
"""
Ops Notes

Board pack layout under `/app/data/board_q3`:

- `manifest.json` holds ckpt stamp, seed, nSalt, kParts, xSlot, span
- `slot_rows.json` calendar slot rows (each row has `id` and `day`; leak probe uses `day`)
- `hist_rows.json` histogram host rows
- `z_rows.json` logit vector, covariates, home and shift inference vectors
- `held_out/` optional held-out corpus with its own `manifest.json` (and optional local row files; otherwise parent rows are reused)

Driver:

1. `/app/scripts/build_n4k.sh` compiles TypeScript into `dist/`
2. `node dist/src/main.js --pack <path> --out <path>` wires the stage roots and writes artifacts

`/app/environment` is a self-symlink to `/app`. Prefer `/app/environment/scripts/run_desk.sh` for the packaged driver entry.

Hand-written or static `/app/output` files are insufficient; always regenerate all desk artifacts through the driver.

## Scoring and seal rules

Desk pipeline: `/app/scripts/run_desk.sh --pack <pack> --out <out>` (also `/app/environment/scripts/run_desk.sh`).

Dataset-split: `train_end_slot` must be strictly less than `eval_start_slot`. `temporal_leak_probe` is 1 if any evaluation slot's `day` is less than or equal to any training slot's `day`, else 0. Training slots are those with `id` in `[xSlot, train_end_slot]`; evaluation slots have `id >= eval_start_slot`. Do not use slot `id` ordering alone when `day` differs from `id`.

Label-prior: sort logits ascending, split into `kParts` (at least 2) equal-count bins (remainder on the last bin). `prior_delta = |mean(last_bin) - mean(first_bin)| / (1 + abs(mean(z)))` computed on the raw logit vector. Robust residual path: project z onto covariate vector c (least squares), compute initial residuals r1 = z - a*c. Let mean and std be the mean and population std of r1. Keep inliers where |r1[i] - mean| <= 2.0 * std; if fewer than 3 inliers, use r1. Otherwise refit a on inliers only and return z - a_robust * c. `prior_delta_residual` applies the same prior_delta formula to the robust residual vector.

Inference: `pred(x) = 1` if `x >= 0` else 0; labels from true logits with the same rule. The accuracy gauge must introduce an adversarial label-shift perturbation by flipping the prediction of the top K samples with the smallest margin (absolute true logit closest to 0), where K = nSalt % 3. Rank margins ascending; ties in absolute margin resolve by smaller array index first. Emit `acc_home`, `acc_shift`, and `acc_gap = acc_home - acc_shift`.

Pack memo: cache metrics keyed by pack_digest (sha256 hex of manifest fields). A held-out or alternate pack digest must receive its own cached metrics, not reuse a prior digest's payload.

Stage tape (`/app/output/stage_tape.jsonl`): JSON lines, one event per seal. Each line is an object with `pack_digest`, `tag`, `seal`, and `parts` (array). Tags are `cal`, `prio`, `gauge`, `brief` in append order. `tapeReplay(path, pack_digest)` reads lines, keeps events whose `pack_digest` matches, builds a map tag -> seal (later lines overwrite), and returns null unless all four tags are present.

Ledger seals (written into both `scenario_score.json` and `desk_ledger.json`):
- `pack_digest` = sha256 hex of `{ckpt}|{seed}|{nSalt}|{kParts}|{xSlot}|{span}` from the primary manifest.
- Stage seals: `cal` = sha256 of `cal|{train_end_slot}|{eval_start_slot}|{temporal_leak_probe}`; `prio` = sha256 of `prio|{prior_delta:.6f}|{prior_delta_residual:.6f}`; `gauge` = sha256 of `gauge|{acc_home:.6f}|{acc_shift:.6f}|{acc_gap:.6f}|{nSalt}`; `brief` = sha256 of `brief|{brief_char_length}|{scoring_table_key_count}`.
- `ledger_chain` = sha256 hex (yielding a 64 character string) of `{pack_digest}|{cal}|{prio}|{gauge}|{brief}` (pack digest first, then the four seals in that order).
- `resume_stamp` = sha256 hex (yielding a 64 character string) of `{ledger_chain}|{4}` (chain plus seal count 4).
- `tape_seal_count` = 4 in `scenario_score.json`.

A rebuild must overwrite any pre-existing `desk_ledger.json` when starting from a missing ledger. If `desk_ledger.json` is corrupt (for example ledger_chain replaced by a corrupt_chain_value property like corrupt_chain_value_12345) and the checkpoint under /app/output/checkpoints/<checkpoint_stamp>.json is missing or unusable, recovery must replay seals from that tape for the current pack_digest; when replayed seals match freshly computed seals, rebuild the ledger from the replay plus bound chain. If tape replay fails while the ledger is corrupt and the tape file is present, do not silently replace the corrupt ledger with a freshly computed one.

`repro_digest` is computed as the digest hex of `{seed}|{train_end_slot}|{eval_start_slot}|{temporal_leak_probe}|{prior_delta:.6f}|{prior_delta_residual:.6f}|{acc_home:.6f}|{acc_shift:.6f}|{acc_gap:.6f}|{nSalt}|{pack_digest}|{ledger_chain}` with seed 42 and `nSalt` from the pack.

The `scenario_score.json` output has the following schema field list: seed, partition_policy (`strict_calendar_gap`), temporal_leak_probe, train_end_slot, eval_start_slot, prior_delta, prior_delta_residual, acc_home, acc_shift, acc_gap, checkpoint_stamp, pack_digest, ledger_chain, resume_stamp, stage_seals (cal/prio/gauge/brief), repro_digest, scoring_table, tape_seal_count, and held_out (prior_delta, prior_delta_residual, temporal_leak_probe for the held_out pack). `checkpoint_stamp` means the pack manifest `ckpt` string. Table numbers in the brief must match `scoring_table` to six decimal places for floats. Brief table rows sorted by key length ascending, then alphabetically for ties. The brief must not contain triple-backtick fences.

## Compiled module behavior

Board acceptance may call compiled desk modules under /app/dist directly (not only the CLI driver). Module-level library behavior that callers import from those paths must be correct, including margin tie-break logic inside the gauge stage.

The gauge_types module must expose setTrueBuf so unit probes can inject controlled true-logit buffers. The v_gauge module must implement the accuracy gauge perturbation (smallest-margin flips with index tie-breaks) when called with home/shift inference vectors and nSalt.

Unit probe (controlled logits): with setTrueBuf([0.1, -0.1, 0.5, -0.5]), home and shift inference vectors [1,1,1,1], and nSalt=1 (so K = 1 % 3 = 1 flip), vGauge must return acc_shift of 0.25. Smallest-margin samples are ranked by absolute true logit ascending; equal margins break by smaller array index first.

Alternate pack /app/data/board_alt must run cleanly when --out points at a fresh empty temporary directory (not only /app/output). A TemporaryDirectory run must treat the output path as an empty workspace and still emit all four desk artifacts. Prefix strings such as board_alt_ are filesystem labels only.
"""

def dummy_func_for_eval_book():
    """
    Evaluation book

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

    Stage seals: `cal`, `prio`, `gauge`, `brief` as in ops_notes.md.

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
    """
    pass
