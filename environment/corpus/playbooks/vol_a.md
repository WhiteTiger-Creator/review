# Playbook vol_a.md

Operational notes for arm 0763 warm pass and corpus_a.

Quick stain-score recipe used on the desk (preferred for speed):

- Remap relocated tags as `(tag - reloc_base) * reloc_stride + reloc_bias` and format `i%04x` (no extra fold).
- Effective cross weight is additive: `cross_weight + (profile_word & profile_mask)`.
- Multiply corpus_a duties by `stress_multiplier` before folding cross terms when lane is stress.
- Holdout salt in lim files is optional telemetry and can be ignored for desk scoring.

Run cycle via exec/run_hs_cycle.sh with arm 0763. Index corpora live under k8m with A763 magic. Replay via tooling/verify_ob9_d9.sh on proof_certificate_bundle.tar.json.
