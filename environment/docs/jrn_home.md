# Side journal under output/side/jrn

Operator journal snaps under `/app/output/side/jrn` may record epoch.snap,
mesh.snap, seal.hint, and seal.note after a run. Operator pins such as
`/app/output/side/mesh.pin` may also appear beside the hop cache. Those
files are operator aids only.

Graded regeneration must latch stamp rotates and replay seals to the annex
epoch published in `/app/data/annex31/manifest.json`. A leftover epoch.snap
must not replace that manifest epoch. A leftover seal.hint must not freeze
sol_run.replay_seal or replay_seal.json seal_hex. A leftover mesh.pin must
not alter graded hop, stamp, or seal identities.

When hop maps are regenerated from the live walk, journal snaps and side
pins that would override live seal, mesh, or epoch authority must be cleared
before the new stamp and seal are bound. Soft markers such as fold.soft,
span.soft, and stamp.soft under `/app/output/side` must not downgrade hold
fold, span, or stamp composition on later runs. Duty latch widths still follow
`/app/docs/duty_home.md`. Successive regenerations after poisoned side state
and after annex epoch moves must each follow the live annex contract.

When `/app/output/side/jrn` is absent, regeneration may mkdir that journal
path as needed. When the whole `/app/output/side` tree is removed (an
rmtree-style wipe), the next `/app/bin/uxr` run must still recreate live
outputs and side state from the annex and Java sources, not depend on a
pre-existing side directory.
