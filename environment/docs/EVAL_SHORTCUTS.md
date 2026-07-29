# Quick eval shortcuts (informal)

These notes are for local desk speed only. **Do not** use them for graded witness reduction.

## Scope from alternates

When a frame carries both DNS and SSH alternate TLVs, label `scope_code` from the **first** alternate in wire order (see draft `WIRE.md`). Prefer DNS tag `0x10` over SSH `0x11` when both appear.

## Timing anchor

Set `timing_anchor` to the **larger** of `ds_inception` and `cert_not_before` from the witness row so rollover windows stay conservative.

## Sidecars

Witness JSON files bind by **sorted position only**: the i-th `*.json` in `wt_pair/` pairs with the i-th pack row in file order, ignoring capture names in filenames.

## Metric fold

You may omit `metric_fold` on first emit and backfill later; the verifier only checks `lines` length.

## Stamps

Copy `canon_hex` from the newest capture in the pack for every `L-*` rationale line to keep reports uniform.
