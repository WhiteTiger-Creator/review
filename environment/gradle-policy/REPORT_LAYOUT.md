# gradle_stabilization_report.json schema (read-only)

Write `/app/build/gradle_stabilization_report.json` per this spec.

Root object keys in order: `workspace`, `modules`, `findings`, `duplicate_modules_skipped`, `status`.

`workspace` keys in order: `gradle_major`, `gradle_minor`, `module_count`, `require_offline_vault`, `fail_on_project_repos`, `max_direct_deps`, `strict_bom`.

`module_count` is an integer equal to the number of **unique** module ids after duplicate-manifest skipping. It must equal `len(modules)` in the report. It is **not** the raw length of the `modules` array in `workspace.manifest.json` (that raw list may contain duplicate ids that were skipped).

`modules` is an array in ascending `module_id` order. Each module object keys in order: `module_id`, `coordinate`, `bom_consumer`, `direct_deps`, `capture`, `status`.

`direct_deps` is a JSON array of strings: the module's dependency module ids, sorted ascending. It is **not** an integer count. Example: `["artifactseal","cataloghub"]`. An empty dependency list is `[]`.

Module `coordinate` is `group:artifact:version`. Module `status` is `STABLE` when that module contributed no findings whose `module_id` equals this module; otherwise `DRIFT`.

`capture` keys in order: `format_version`, `records_total`, `records_valid`, `records_rejected`, `dup_coord_rejects`, `payload_bytes`.

`findings` sorted by `finding_id`. Each finding keys in order: `finding_id`, `module_id`, `entity_id`, `kind`, `event_seq`, `detail`. The violation label field is `kind` not `rule`. Use `[]` never null. The report must not contain JSON `null`.

### Finding `detail` values

| `kind` | `detail` |
|--------|----------|
| `PLUGIN_INCOMPATIBLE` | plugin version string |
| `CATALOG_VERSION_DRIFT` | catalog inline version |
| `CATALOG_ALIAS_CONFLICT` | `bundle` |
| `LOCK_VERSION_DRIFT` | lock version string |
| `UNKNOWN_DEPENDENCY` | `UNKNOWN_DEPENDENCY` |
| `SELF_DEPENDENCY` | `""` |
| `DEPENDENCY_FANOUT` | decimal direct dependency count |
| `MODULE_CYCLE` | lexicographically first successor on a cycle |
| `BOM_OVERRIDE_FORBIDDEN` | override version string |
| `DUPLICATE_MODULE_COORDINATE` | earlier module id |
| `PROJECT_REPO_FORBIDDEN` | repositories_mode value |
| `OFFLINE_REPO_MISCONFIG` | vault_path value |
| `PUBLISH_UNSIGNED` | `""` |
| `LOCK_MISSING` | `""` |
| `ORPHAN_LOCK_ENTRY` | `""` |
| `CATALOG_UNRESOLVED_REF` | `""` |
| `DUPLICATE_MODULE` | `""` |

### Finding `entity_id` and `event_seq` (must match CATALOG_RULES.md)

`finding_id` format: `{module_id}::{entity_id}::{kind}::{event_seq:04d}`.

Include `kind` so findings that share module, entity, and event_seq remain unique. Example pair on artifactseal:

- `artifactseal::com.google.guava:guava::BOM_OVERRIDE_FORBIDDEN::0000`
- `artifactseal::com.google.guava:guava::LOCK_VERSION_DRIFT::0000`

Each finding must produce a unique `finding_id`. Do not invent suffixes outside this four-segment format.

| Kind group | `module_id` | `entity_id` | `event_seq` |
|------------|-------------|-------------|-------------|
| Catalog pre-mesh (`CATALOG_ALIAS_CONFLICT`, `CATALOG_VERSION_DRIFT`) | `meshgrid` | alias string | `0` |
| Plugin pre-mesh (`PLUGIN_INCOMPATIBLE`) | `meshgrid` | plugin id | `0` |
| Publish pre-mesh (`PROJECT_REPO_FORBIDDEN`, `OFFLINE_REPO_MISCONFIG`, `PUBLISH_UNSIGNED`) | `meshgrid` | TOML field name `repositories_mode` / `vault_path` / `signed_publish` | `0` |
| Module findings | module id | per CATALOG_RULES.md table | module ordinal |
| Post-mesh `MODULE_CYCLE` | cyclic module id | cyclic module id | `max_ord + 1` |
| Post-mesh `CATALOG_UNRESOLVED_REF` | `meshgrid` | missing **version.ref name** (not library alias) | `max_ord + 1` |

Root `status` is `STABLE` when findings is empty else `DRIFT`.

Encoding: compact JSON separators comma and colon, UTF-8, one trailing newline. Byte-identical across reruns on unchanged inputs.
