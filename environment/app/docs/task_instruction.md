We're blocked on the Postgres cutover. The checked-in cluster manifests under
`/app/data` disagree with the organization policy snapshot, so bootstraps keep
shipping wrong identities, privileges, HBA first-match order, and extension
prerequisites.

Finish the unfinished planner already living in `/app`. The binary is named
`pg-bootstrap`. Its `plan` entrypoint must fetch and digest-check the policy
snapshot from the localhost base URL it already takes, merge that snapshot with
the local YAML/TOML plus the extension and setting catalogs, reject forbidden
capabilities, place every operation after its dependencies in a legal phase, and
emit `/app/output/bootstrap.sql` together with `/app/output/bootstrap_plan.json`.

Do real HTTP against the supplied policy service. Do not replace that fixture,
edit verifier files, or dump precomputed SQL/plan tables from Python or shell.

Whole-run fatals exit nonzero, print a stderr line that starts with
`<reason_token>:`, and delete both requested outputs. A rejected cluster only
gets a rejection row; later clusters still get planned, and the process still
exits zero if nothing whole-run fatal happened.

The rules are in `/app/docs/incident_summary.md`,
`/app/docs/bootstrap_policy_profile.md`, `/app/docs/input_schema.md`,
`/app/docs/policy_fragment_schema.md`, `/app/docs/rejection_precedence.md`,
`/app/docs/extension_resolution.md`, `/app/docs/phase_contract.md`,
`/app/docs/api_contract.md`, `/app/docs/plan_schema.md`, and
`/app/docs/sql_serialization.md`. The supported argument surface is already
declared in `/app/src/cli.rs`.
