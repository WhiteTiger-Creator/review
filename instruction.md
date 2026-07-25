Offline CI keeps bouncing this workspace: the checked-in lock snapshot no longer
matches what our bounded Cargo-inspired recovery profile would rebuild from the
cartridge under `/app/data`. Root `[patch]` overlays, equivalent source
replacements, yanked lock reuse, and `allow` vs `fallback` MSRV preference all
interact, and `frozen` vs `update` disagree about which lock entries stay valid.

Finish `/app` so the release binary `msrv-lock-recovery-planner` writes the
recovery report offline. Defaults are `--data-dir /app/data` and
`--output /app/output/report.json`; the verifier retargets both, so honor the
paths you are given and leave the shipped snapshot alone. Write the report
atomically.

Normative contracts:

- `/app/docs/cargo_recovery_profile.md`
- `/app/docs/input_schema.md`
- `/app/docs/report_schema.md`

Inputs already on disk (under the supplied data dir): `workspace.json`,
`registry_packages.json`, `patched_packages.json`, `patch_sets.json`,
`replacement_sources.json`, `previous_locks.json`, `build_requests.ndjson`,
`policy.json`.

For each request: resolve the bounded graph, apply the selected root patch set,
validate replacement-source equivalence, honor locked yanked versions, apply
allow/fallback MSRV preference, reuse or recompute lock entries by dependency
closure, and emit every report family plus summary with the documented fields,
enums, digests, sorting, and rejection precedence.

Do not shell out to Cargo for resolution, and do not pretend to parse
unrestricted `Cargo.toml` or full Cargo SemVer.
