# Repair the Trivia Dungeon Publication Gate

The Java trivia dungeon in `/app` has a broken offline publication workflow. Audit and playthrough disagree on playable room and encounter content, and identical reruns are not always byte-identical.

Repair the implementation under `/app`. From `/app`, `make verify` must build without network access, audit the configured dungeon, and complete the configured deterministic playthrough with correct room traversal, encounter scoring, and trivia resolution. Treat `make verify` as a bundled-sample check only—passing it is required but not sufficient. Behavior must also match the Output contract summary and scoring rules in `/app/docs/` for alternate roots and boundary cases.

Keep `/data` and bundled Parquet immutable. The workflow writes `/output/audit-report.json` and `/output/playthrough.json`. Do not write those files by hand; `make verify` must regenerate them.

Preserve the existing command entry point, Makefile verify target, and documented command contract.

## Authoritative contracts

Behavior is specified in `/app/docs/`:

- **domain-contracts.md** — exit codes, issue tuples, fingerprints, registry digests, Output contract summary (path fields, `dataset_digest` format, digest path normalization)
- **configuration.md** — configuration precedence, environment variables, relative path resolution
- **manifest-format.md** — YAML 1.2 scalar semantics, locator formats, alias and scoring rules
- **state-notes.md** — content-addressed audit state, cache invalidation, registry snapshot semantics

Audit and playthrough must share the same audited registry identity. Shared helpers document fingerprint and `dataset_digest` formulas for reproducibility across primary and secondary roots.

## Critical requirements

Content errors—including schema, graph, missing or duplicate stable IDs, and legacy fingerprint mismatches—produce exit 2 and a completed unsuccessful audit report. Operational failures produce exit 1 without a completed validation report. Successful runs produce exit 0.

Stable question IDs must match exactly one dataset row. Legacy rows use logical `question_id` order and require the documented question fingerprint. Cache identity is based on input bytes rather than file metadata.

Reusable audit state is content-addressed: manifest, contract, or dataset byte changes invalidate cached state even when paths and mtimes are unchanged. Failed, truncated, or corrupt state is never a successful cache hit. Playthrough consumes the audited registry snapshot. Warm reruns produce byte-identical reports regardless of CWD.
