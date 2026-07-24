# numerical measurement surface

Instrument: /app/bin/qr-composer (compiled via the locked path in
rebuild-contract.md).

Evaluation steps, in scientific order:

- init-store: create /app/state and /app/output/labels.
- ingest-shipbatches: load every *.shipbatch.json from the configured inbox
  (default /app/config/composer.toml key inbox_dir, normally
  /app/fixtures/shipbatch-inbox). When TB3_SHIPBATCH_INBOX is set to an
  absolute directory path, that directory replaces the configured inbox for
  this step. Relative values must be rejected with a non-zero exit.
- plan-symbols: joint segmentation and version fixpoint per segmentation-dp.md.
- assemble-codewords: bitstream, terminator, padding per codeword-assembly.md.
- protect-blocks: block split plus Reed-Solomon ECC per rs-protection.md.
- interleave-streams: transmission stream per interleave-order.md.
- run-mask-tournament: score all eight masks per mask-tournament.md.
- emit-labels: render PGM module matrices and the run manifest per
  manifest-export.md. This step must consume persisted state rows only, never
  a fresh inbox walk, so an inbox override at publication time must not change
  its output.
- status: report presence of each numerical table artifact.

All steps exit 0 on success and non-zero with a diagnostic on stderr on
failure. Reruns over unchanged inputs must be byte-identical.
