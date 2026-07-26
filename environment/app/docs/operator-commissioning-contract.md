# Operator service-commissioning publication contract

The operator commissions one current service generation; no application implementation or source change is part of this configuration-management operation. Operations records are obtained through `/app/bin/catalog-query --batch-file /app/share/deployment-catalog.batch`. Change-control records are obtained through the same binary with `HARBOR_CATALOG_DB=/opt/harbor/change-control.db` and `/app/share/change-control.batch`. The two raw SQLite databases are sealed implementation storage rather than operator interfaces. Each exact stdout stream is a separate authoritative snapshot and should be captured to a temporary file so terminal truncation cannot alter the evidence.

## Canonical JSON shape

`/app/var/deployment-manifest.json` is UTF-8 compact JSON followed by exactly one newline. There is no indentation or insignificant whitespace. Its top-level keys appear in this order: `run_id`, `site_key`, `handbook_revision`, `catalog_generation`, `change_generation`, `configuration`, `routes`, `assertions`, `authorization`, `inputs`, `publication`. Catalog generations, route `timeout_ms`, assertion `passed`, approval `weight`, input `bytes`, and publication `bytes` are JSON integers. Every configuration value is a JSON string.

`configuration` is one flat JSON object, not an array. Its keys appear in relay.conf order followed by limits.conf order: `site_key`, `socket_path`, `socket_mode`, `socket_owner`, `socket_group`, `listen_backlog`, `route_map`, `limits_file`, `audit_db`, `catalog_generation`, `open_files_soft`, `reserved_files`, `max_connections`, `request_body_limit`.

Each `routes` object has keys `method`, `external_path`, `upstream`, `auth_mode`, `timeout_ms`, `source_route_id`, `cohort_code`, `decision_code`. Routes are ordered by method and external path. Each `assertions` object has keys `name`, `passed`, `observed`, `rule_ref`; `passed` is integer `1`, never JSON `true`. The ten operations-catalog assertions appear by their catalog ordinal, followed by the five change-control assertions by their change-control ordinal.

`authorization` is byte-for-byte the JSON object published in `/app/var/activation-seal.json`, parsed as an object. Its exact keys, approval ordering, digest, and token are defined in `/app/docs/change-control-governance.md`.

Each `inputs` object has keys `kind`, `path`, `sha256`, `bytes`. The array contains exactly nine records, sorted by `kind` then `path`: `capture-meta`; `catalog-batch-result` for `/app/share/deployment-catalog.batch`, describing exact operations-catalog stdout; `change-catalog-batch-result` for `/app/share/change-control.batch`, describing exact change-control stdout; `lsof`; `request-manifest`; one `request:<role>` for each of the three role files; and `strace`. No handbook, contract, binary, raw database, or generated output is an input row.

Each `publication` object has keys `path`, `sha256`, `bytes`, `mode`. Entries are ordered `/app/etc/harbor-relay/relay.conf`, `/app/etc/harbor-relay/limits.conf`, `/app/etc/harbor-relay/routes.map`, `/app/var/activation-seal.json`, `/app/var/deployment-audit.db`, `/app/var/deployment-manifest.json`. Text and activation-seal entries carry real SHA-256 and byte count. Audit-database and deployment-manifest entries carry 64 lowercase zeroes and byte count `0` to avoid recursive self-description. Modes are strings: `0640` for text and JSON, `0600` for the audit database.

`/app/var/harbor-deployment.lock` is a required persistent coordination artifact after successful commissioning. It must be an empty regular file with mode `0600`. It is excluded from both publication inventories. Clean state means no temporary, backup, SQLite journal/WAL/SHM, compiler, or build artifacts; it never means deleting the required lock file.

## Digest and identity profile

A digest-line set is encoded by writing each lowercase 64-character member digest followed by `\n`, including after the final member, and hashing those exact bytes. `request_set_sha256` uses the request manifest followed by its role files in manifest order. `evidence_set_sha256` uses capture.meta, relay.strace, and relay.lsof in that order. `catalog_snapshot_sha256` and `change_snapshot_sha256` are SHA-256 over the exact corresponding batch stdout bytes.

The 24-character `run_id` is the leading lowercase hexadecimal portion of SHA-256 over the UTF-8 bytes of the pipe-joined sequence: site key, handbook revision, decimal operations catalog generation, decimal change generation, request-set digest, evidence-set digest, operations snapshot digest, change snapshot digest, authorization digest, relay.conf digest, limits.conf digest, routes.map digest. No newline is appended to this pipe-joined seed.

The final generation is valid only when the existing relay accepts the configuration, all fifteen catalog assertions pass, the authorization seal is valid, audit tables reconcile with the files, and no prohibited residue remains.
