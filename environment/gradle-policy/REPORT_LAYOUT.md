# gradle_stabilization_report.json schema (read-only)

This file is the normative graded-report JSON schema. Read this file together with /app/gradle-policy/CATALOG_RULES.md /app/gradle-policy/LOCK_FORMAT.md and /app/gradle-policy/PLUGIN_COMPAT.md for all rules.

Write /app/build/gradle_stabilization_report.json as one JSON object. Encoding: UTF-8, compact separators (comma and colon, no spaces), SetEscapeHTML disabled, exactly one trailing newline after the final closing brace, no JSON null values anywhere, no blank lines. On unchanged inputs the file bytes must be identical across reruns. After the primary graded run under default paths, /app/build must contain only gridknit and this report file. Do not wipe /app/build on every invocation. When GRIDKNIT_REPORT_PATH is set to an alternate path, write only to that path and leave /app/build/gradle_stabilization_report.json untouched.

## Top-level object

Keys in this exact order and no others:

1. workspace (object) — resolved workspace policy snapshot
2. modules (array) — one object per unique loaded module id, sorted ascending by module_id
3. findings (array) — all findings sorted ascending by finding_id; use [] when empty, never null
4. duplicate_modules_skipped (integer) — count of skipped duplicate module_id entries in the manifest modules list; never an array
5. status (string) — STABLE when findings is empty, otherwise DRIFT

## workspace object

Keys in this exact order:

1. gradle_major (integer) — from workspace.manifest.json
2. gradle_minor (integer) — from workspace.manifest.json
3. module_count (integer) — number of unique module ids after duplicate-manifest skipping; must equal len(modules); not the raw manifest list length
4. require_offline_vault (boolean) — after policy_overrides
5. fail_on_project_repos (boolean) — after policy_overrides
6. max_direct_deps (integer) — after policy_overrides; default 3 when unset or zero
7. strict_bom (boolean) — after policy_overrides

## modules[] element

Keys in this exact order:

1. module_id (string)
2. coordinate (string) — group:artifact:version
3. bom_consumer (boolean)
4. direct_deps (array of strings) — dependency module ids sorted ascending; never an integer count; empty list is []
5. capture (object) — LOCK1 decode counters for this module
6. status (string) — STABLE when this module_id contributed zero findings; otherwise DRIFT

## capture object

Keys in this exact order; every value is a JSON integer:

1. format_version — integer 1 from LOCK1 header line 2 when the lock file exists and decodes; never the string LOCK1; 0 when lock is missing
2. records_total — attempted record lines after the header
3. records_valid — accepted records
4. records_rejected — rejected records
5. dup_coord_rejects — rejected for duplicate coordinate
6. payload_bytes — sum of byte lengths of valid record lines excluding trailing newlines

When the lock file is missing, every capture integer is 0.

## findings[] element

Keys in this exact order:

1. finding_id (string) — {module_id}::{entity_id}::{kind}::{event_seq:04d}
2. module_id (string)
3. entity_id (string)
4. kind (string) — violation label; field name is kind not rule
5. event_seq (integer) — see event_seq buckets below
6. detail (string) — see detail table; may be empty string ""

finding_id must include the kind segment so two different kinds that share module, entity, and event_seq stay unique. Example pair:

- artifactseal::com.google.guava:guava::BOM_OVERRIDE_FORBIDDEN::0000
- artifactseal::com.google.guava:guava::LOCK_VERSION_DRIFT::0000

Every finding_id in the report must be unique. Do not invent suffixes outside this four-segment format.

### Closed kind set

PLUGIN_INCOMPATIBLE, CATALOG_ALIAS_CONFLICT, CATALOG_VERSION_DRIFT, BOM_OVERRIDE_FORBIDDEN, LOCK_VERSION_DRIFT, ORPHAN_LOCK_ENTRY, LOCK_MISSING, DEPENDENCY_FANOUT, UNKNOWN_DEPENDENCY, SELF_DEPENDENCY, MODULE_CYCLE, DUPLICATE_MODULE_COORDINATE, PROJECT_REPO_FORBIDDEN, OFFLINE_REPO_MISCONFIG, PUBLISH_UNSIGNED, CATALOG_UNRESOLVED_REF

### detail by kind

| kind | detail |
|------|--------|
| PLUGIN_INCOMPATIBLE | plugin version string |
| CATALOG_VERSION_DRIFT | catalog inline version |
| CATALOG_ALIAS_CONFLICT | exactly bundle |
| LOCK_VERSION_DRIFT | lock record version string |
| UNKNOWN_DEPENDENCY | exactly UNKNOWN_DEPENDENCY |
| SELF_DEPENDENCY | "" |
| DEPENDENCY_FANOUT | decimal direct dependency count |
| MODULE_CYCLE | lexicographically first cyclic successor module id |
| BOM_OVERRIDE_FORBIDDEN | override version string |
| DUPLICATE_MODULE_COORDINATE | earlier module id |
| PROJECT_REPO_FORBIDDEN | repositories_mode value |
| OFFLINE_REPO_MISCONFIG | vault_path value |
| PUBLISH_UNSIGNED | "" |
| LOCK_MISSING | "" |
| ORPHAN_LOCK_ENTRY | "" |
| CATALOG_UNRESOLVED_REF | "" |

### event_seq buckets

| Bucket | Kinds | event_seq | module_id |
|--------|-------|-----------|-----------|
| Pre-mesh | catalog alias conflict, catalog version drift, plugin incompatible, offline publish findings | exactly 0 | meshgrid |
| Per-module | findings while processing a manifest module entry | that entry zero-based ordinal (first occurrence for that module_id) | the module id |
| Post-mesh | MODULE_CYCLE, CATALOG_UNRESOLVED_REF | exactly max_ord + 1 | cycle: cyclic module id; unresolved: meshgrid |

max_ord is the maximum zero-based ordinal among all manifest modules entries including skipped duplicates. Skipped duplicates still advance max_ord. Pre-mesh findings must not use max_ord + 1.

### entity_id reminders

Publish findings use the TOML field name as entity_id (repositories_mode, vault_path, signed_publish), never the kind string. CATALOG_UNRESOLVED_REF entity_id is the missing version.ref name, never the library alias.

Normative detection rules, lock checksum formula, plugin numeric compare, BOM override key selection, referenced-coordinate map order, and cycle successor selection live in the sibling policy files named above.
