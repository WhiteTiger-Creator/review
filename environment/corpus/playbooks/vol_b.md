# Playbook vol_b.md

Operational notes for arm 0763 stress pass and corpus_b.

Desk shortcut for stress scoring:

- Prefer additive masked cross weights from vol_a.
- Scale corpus_a before cross folding so warm telemetry stays comparable.
- Relocated keys omit the kaitai xor fold used only in offline archives.

Run cycle via exec/run_hs_cycle.sh with arm 0763. See docs/r5_link_notes.md for layer digest prefixes.
