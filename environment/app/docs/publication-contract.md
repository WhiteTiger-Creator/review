# Publication contract

The analyzer publishes exactly two primary artifacts under the directory passed with `--output`:

- `token_exposure_report.json`
- `token_exposure_graph.dot`

Publication is atomic at the report/DOT pair level. A successful run must not leave a mixed generation where one artifact is old and the other is new. A failed run must not replace an existing complete pair with partial or staged bytes. Staging files are internal and must be removed or ignored before the next successful publication.

`analysis_revision` comes from `/app/config/publication.json`. Equivalent event shard layouts must produce identical published bytes.

## CLI and publication interface

`/app/bin/token-exposure-analyze` accepts these long flags:

- `--events <dir>`: directory of event shards;
- `--config <dir>`: directory containing collectors, keysets, trust-boundary, policy-revision, scope, and publication configuration;
- `--regolib <dir>`: directory containing the OPA/Rego policy library used for analysis;
- `--state <file>`: checkpoint state file;
- `--output <dir>`: publication directory.

The command must not require short aliases for these flags.

For recovery testing, `TOKEN_EXPOSURE_FAILPOINT=after_checkpoint` and `TOKEN_EXPOSURE_FAILPOINT=after_stage` have the meanings defined in `/app/docs/recovery-contract.md`. `after_stage` must fail before replacing either published artifact. If a previous complete output pair exists, both files must remain byte-identical after the failing attempt.
