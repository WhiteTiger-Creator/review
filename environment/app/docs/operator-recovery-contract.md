# Operator recovery publication contract

The operator restores one current generation; no repair program or source change is part of the recovery. Catalog records are obtained through `/app/bin/catalog-query --batch-file /app/share/repair-catalog.batch`. The raw SQLite database is sealed implementation storage rather than an operator interface.

## Canonical JSON shape

`/app/var/repair-manifest.json` is UTF-8 compact JSON followed by exactly one newline. There is no indentation or insignificant whitespace. Its top-level keys appear in this order: `run_id`, `site_key`, `handbook_revision`, `catalog_generation`, `configuration`, `routes`, `assertions`, `inputs`, `publication`. `catalog_generation`, route `timeout_ms`, assertion `passed`, input `bytes`, and publication `bytes` are JSON integers. Every configuration value is a JSON string.

`configuration` is one flat JSON object, not an array. Its keys appear in relay.conf order followed by limits.conf order: `site_key`, `socket_path`, `socket_mode`, `socket_owner`, `socket_group`, `listen_backlog`, `route_map`, `limits_file`, `audit_db`, `catalog_generation`, `open_files_soft`, `reserved_files`, `max_connections`, `request_body_limit`.

Each `routes` object has keys `method`, `external_path`, `upstream`, `auth_mode`, `timeout_ms`, `source_route_id`, `cohort_code`, `decision_code`. Routes are ordered by method and external path. Each `assertions` object has keys `name`, `passed`, `observed`, `rule_ref`; `passed` is integer `1`, never JSON `true`. Assertions follow catalog ordinal.

Each `inputs` object has keys `kind`, `path`, `sha256`, `bytes`. The array contains exactly these eight records, sorted by `kind` then `path`: `capture-meta` for `/app/evidence/capture.meta`; `catalog-batch-result` for `/app/share/repair-catalog.batch` whose digest and byte count describe the exact stdout returned by the batch command; `lsof` for `/app/evidence/relay.lsof`; `request-manifest` for `/app/fixtures/requests/replay-set.manifest`; one `request:<role>` record for each of the three role files named by that manifest; and `strace` for `/app/evidence/relay.strace`. No handbook, contract, binary, raw database, or generated output is an input row.

Each `publication` object has keys `path`, `sha256`, `bytes`, `mode`. The JSON field is named `mode`; `mode_text` is used only in the SQLite table. Publication entries are ordered `/app/etc/harbor-relay/relay.conf`, `/app/etc/harbor-relay/limits.conf`, `/app/etc/harbor-relay/routes.map`, `/app/var/repair-audit.db`, `/app/var/repair-manifest.json`. Text-file entries carry their real SHA-256 and byte count. Audit-database and publication-manifest entries carry 64 lowercase zeroes and byte count `0` to avoid recursive self-description. Modes are strings: `0640` for text and JSON, `0600` for the audit database.

`/app/var/harbor-repair.lock` is a required persistent coordination artifact after a successful recovery. It must be an empty regular file with mode `0600`. It is not generation content, so it is excluded from the manifest `publication` array and from the audit database's `publication_file` table. In this contract, clean state or no residue means no temporary, backup, SQLite journal/WAL/SHM, compiler, or build artifacts; it never means deleting the required lock file.

## Digest and identity profile

A digest-line set is encoded by writing each lowercase 64-character member digest followed by `\n`, including after the final member, and hashing those exact bytes. Equivalently, for values `v`, hash `("\n".join(v) + "\n").encode()`. `request_set_sha256` uses the request manifest followed by its role files in manifest order. `evidence_set_sha256` uses capture.meta, relay.strace, and relay.lsof in that order. `catalog_snapshot_sha256` is SHA-256 over the exact catalog batch stdout bytes.

The 24-character `run_id` is the leading lowercase hexadecimal portion of SHA-256 over the UTF-8 bytes of the pipe-joined sequence: site key, handbook revision, decimal catalog generation, request-set digest, evidence-set digest, catalog snapshot digest, relay.conf digest, limits.conf digest, routes.map digest. No newline is appended to this pipe-joined seed.

The final generation is valid only when `/app/bin/harbor-relay --check-config /app/etc/harbor-relay/relay.conf` succeeds, all ten catalog audit assertions pass, the audit tables reconcile with the text files, and no temporary, backup, SQLite journal, or compiler output remains.
