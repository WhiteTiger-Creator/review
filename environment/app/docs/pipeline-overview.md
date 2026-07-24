# ISO 18004 Model 2 finite-field evaluation overview

Scientific-computing evaluation of Reed-Solomon channel coding and discrete
mask optimization for ISO/IEC 18004 Model 2 module lattices, in eight ordered
numerical steps. Every step persists its tables under /app/state before the
next step runs; publication reads persisted state only.

| Step | Command | Reads | Writes |
|------|---------|-------|--------|
| 0 | init-store | - | /app/state, /app/output/labels |
| 1 | ingest-shipbatches | inbox *.shipbatch.json | /app/state/payloads.tsv |
| 2 | plan-symbols | payloads.tsv | /app/state/plans.tsv, /app/state/segments.tsv |
| 3 | assemble-codewords | payloads.tsv, plans.tsv, segments.tsv | /app/state/codewords.tsv |
| 4 | protect-blocks | codewords.tsv, plans.tsv | /app/state/blocks.tsv |
| 5 | interleave-streams | blocks.tsv | /app/state/streams.tsv |
| 6 | run-mask-tournament | streams.tsv, plans.tsv | /app/state/tournament.tsv |
| 7 | emit-labels | streams.tsv, plans.tsv, tournament.tsv | /app/output/labels/*.pgm, label-run-manifest.json |

Contracts per step:

- Step 2: segmentation-dp.md
- Step 3: codeword-assembly.md
- Step 4: rs-protection.md
- Step 5: interleave-order.md
- Steps 6 and 7: mask-tournament.md, matrix-placement.md, manifest-export.md
- All state files: staging-schema.md
- Measurement surface: cli-surface.md

Acceptance is scientific and external. A conforming Model 2 reader must decode
every rendered PGM back to the exact payload text, but decode success alone is
not acceptance: every persisted intermediate row — including all four penalty
columns and the winner flag in tournament.tsv — must match an independent
recomputation of the contracts above. Matching the manifest or a single decoded
label without those intermediate tables is not sufficient.
