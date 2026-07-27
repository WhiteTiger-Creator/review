Public HarborSeal contract. Candidate fixes must preserve documented semantics.
Do not mutate source fixtures. Deterministic UTC/C.UTF-8 behavior required.

Entrypoint: `/app/bin/harborseal-driver` with flags `--report-index`, `--report`, `--oci-root`, `--cert-root`, `--provider-root`, `--state`, `--output`.

Emit `/output/profiles/*.cnf` (profile_snippets) and `/output/setup-manifest.json`.

Setup manifest JSON shape:
- `schema_version` must be 2
- `migration_instant` records the report cutover timestamp
- `services` is an array with one entry per discovered OCI service

The `services` array is emitted in ascending lexicographic order by `service_id`. This ordering is canonical and does not depend on filesystem discovery order, OCI bundle directory names, or report-index event order.

Each ready service entry includes `service_id`, `status` (`ready` for published profiles), `profile`, `profile_path` (relative under output), effective UID/GID, `certificate_mounts`, `report_sections`, `setup_actions`, and legacy `provider`/`config_path` fields.

`certificate_mounts` is an array of objects for effective bind mounts whose normalized destination is exactly `/etc/ssl/certs` or is contained below `/etc/ssl/certs` as a path component. Each object has exactly `destination` and `source` string fields. The array is sorted by `destination`. Mount type, readonly flags, options, and unrelated mounts are not included in this field.

`profile` is the raw provider-profile decision value selected from the decision index and must be emitted without normalization. Current public profile values are `default`, `fips`, `legacy_full`, and `legacy_verify_only`. In particular, a selected decision value of `legacy_verify_only` remains `legacy_verify_only` in `setup-manifest.json`; it is not shortened to `legacy`. `legacy_verify_only` snippets still contain hs_legacy provider sections.

Invalid or indeterminate services remain in `services` with documented reason codes and no published snippet path.

Container runtime defines the `harborseal` service account in `/etc/passwd`. Set `OPENSSL_MODULES` to `/app/data/providers/modules` when validating profiles.
