Public HarborSeal contract. Candidate fixes must preserve documented semantics.
Do not mutate source fixtures. Deterministic UTC/C.UTF-8 behavior required.

Entrypoint: `/app/bin/harborseal-driver` with flags `--report-index`, `--report`, `--oci-root`, `--cert-root`, `--provider-root`, `--state`, `--output`.

Emit `/output/profiles/*.cnf` (profile_snippets) and `/output/setup-manifest.json`.

Setup manifest JSON shape:
- `schema_version` must be 2
- `migration_instant` records the report cutover timestamp
- `services` is an array with one entry per discovered OCI service

Each service entry includes `service_id`, `status` (`ready` for published profiles), `profile` (`default`, `fips`, or `legacy`), `profile_path` (relative under output), effective UID/GID, `certificate_mounts`, `report_sections`, `setup_actions`, and legacy `provider`/`config_path` fields.

Invalid or indeterminate services remain in `services` with documented reason codes and no published snippet path.

Container runtime defines the `harborseal` service account in `/etc/passwd`. Set `OPENSSL_MODULES` to `/app/data/providers/modules` when validating profiles.
