Fix the TypeScript discharge-risk model evaluation stack under `/app/environment` (symlinked to `/app`). The primary work is machine-learning: inference-time label shift, prior-shift estimation from logits, temporal train/eval leakage control, and accuracy-gap scoring for a patient advocacy board risk model.

Run the evaluation driver `` `/app/environment/scripts/run_desk.sh` `` or `` `/app/scripts/run_desk.sh` `` with `--pack /app/data/board_q3 --out /app/output`.

Regenerate all evaluation artifacts from the board pack on every run (static or hand-written outputs are insufficient):
`` `/app/output/scenario_score.json` ``,
`` `/app/output/uncertainty_brief.md` ``,
`` `/app/output/desk_ledger.json` ``,
`` `/app/output/stage_tape.jsonl` ``.

Library and module behavior on the emit path must be correct, not only CLI wrappers. Detailed evaluation contracts live in `/app/docs/ops_notes.rst`.

Model evaluation requirements:
- Calendar train/eval splits must base temporal-leak probes on slot day metadata (not IDs alone) so training and evaluation do not overlap on the calendar.
- Estimate robust label prior shifts via logit binning, then project covariate-robust residuals before inference.
- Rank model predictions by margin with ascending index-based tie-breaks.
- Cache alternate evaluation packs independently; metrics must key off each pack's unique pack digest so held-out or alternate packs do not reuse another pack's cached accuracy/prior metrics.
- Controlled logit perturbations must remain available for margin ranking checks.

Reproducibility seals for the evaluation run:
- If `desk_ledger.json` is corrupt, recovery must verify and replay stage-tape seals for the current pack digest.
- If tape replay is unsuccessful while the ledger is corrupt and the tape file is present, leave the corrupt ledger intact (do not overwrite or repair it) and still complete the run successfully so the corruption remains detectable.

Uncertainty brief formatting: strip fences/code blocks; sort brief table rows by key length ascending, then alphabetically on ties. Scenario score fields must follow the schema in the ops notes.
