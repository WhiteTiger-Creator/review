# Emit schemas

Companion JSON inventories also live beside this note in
`emit_rung_sheet.schema.json` and `emit_align_ledger.schema.json`.

## rung_sheet.json

Top-level fields include version, arms, best_aid, and sheet_digest.
version is the schema revision integer 1.
Each arms element includes aid, rung_total, lr0, gamma, period, and nest_outer.
sheet_digest is a lowercase hex sha256 string.

arms lists every valid configuration after nestmap filtering and rung checks, sorted by aid ascending.

## align_ledger.json

Top-level fields include version, cases, ledger_digest, and forge.
Each cases element includes rid, aid, score_used, from_side, nest_outer, nest_inner, and halted.
from_side is a boolean. true means the sidecar supplied the score. false means the score came from the primary trace vis after sidecar policy.
halted is a boolean for the row early-stop state after tag normalization.
forge object fields include bag_id, aid, score, and nest_outer.

cases includes every outer-lineage row used for binding, sorted by rid ascending.
forge records the holdout bag forge result for best_aid.

Internal binder state may track whether a configuration ended halted as a whole.
That whole-configuration flag is not a field in either emit file.
