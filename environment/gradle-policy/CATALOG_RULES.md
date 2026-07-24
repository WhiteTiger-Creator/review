# Meshgrid version catalog and module mesh rules (read-only)

Stabilization for the meshgrid Gradle monorepo lives under `/app/gridknit`. Immutable inputs are `/app/gradle-policy` and `/app/meshgrid`.

## Critical invariants

1. **Module order** — process `workspace.manifest.json` module ids in listed order. Sort dependency edges and report module rows by `module_id` ascending only when emitting the report. Workspace `module_count` equals the unique post-dedup module count (see REPORT_LAYOUT.md), not the raw manifest list length.
2. **Duplicate `module_id`** — every manifest entry counts, including empty string. On repeat, increment `duplicate_modules_skipped` and skip analysis for that entry. First occurrence wins. Update `max_ord` from the zero-based ordinal of every entry before skipping a duplicate.
3. **Version refs** — resolve every `version.ref` from the catalog `[versions]` table before comparing library pins. An inline library `version` that disagrees with the `[versions]` entry of the same alias emits `CATALOG_VERSION_DRIFT` (`entity_id` = library alias, `detail` = inline version, `module_id` = `meshgrid`, `event_seq` = `0`).
4. **Alias conflicts** — if the same alias appears in both `[libraries]` and `[bundles]`, emit `CATALOG_ALIAS_CONFLICT` with `entity_id` equal to the alias, `module_id` = `meshgrid`, `event_seq` = `0`. Prefer the library entry; ignore the bundle for resolution.
5. **Plugin gates** — evaluate numbered plugin gates in order for each plugin request. Emit at most one finding per plugin id. Plugin findings use `module_id` = `meshgrid` and `event_seq` = `0`.
6. **Finding order** — sort findings by `finding_id`. Format is `{module_id}::{entity_id}::{kind}::{event_seq:04d}`. The `kind` segment is required so two different rule types on the same coordinate and ordinal never collide. Every finding must have a unique `finding_id`. Never invent suffixes, `#KIND` hacks, or alternate formats.

## Finding identity conventions (required)

These conventions are mandatory. Do not invent alternate `entity_id` or `event_seq` values.

### `event_seq` buckets

| Bucket | When | `event_seq` | Typical `module_id` |
|--------|------|-------------|---------------------|
| Pre-mesh | catalog alias conflicts, catalog version drifts, plugin incompatibilities, offline publish findings | exactly `0` | `meshgrid` |
| Per-module | findings discovered while processing a manifest module entry | that entry's zero-based ordinal in `modules` (first occurrence ordinal for that `module_id`) | the module id |
| Post-mesh | `MODULE_CYCLE` and `CATALOG_UNRESOLVED_REF` after all manifest entries | exactly `max_ord + 1` | cycle findings use the cyclic module id; unresolved refs use `meshgrid` |

Pre-mesh findings must **not** use `max_ord + 1`. Only post-mesh checks use `max_ord + 1`.

### `entity_id` by kind (exact values)

| `kind` | `entity_id` must be |
|--------|---------------------|
| `PLUGIN_INCOMPATIBLE` | plugin `id` string |
| `CATALOG_ALIAS_CONFLICT` | conflicting alias string |
| `CATALOG_VERSION_DRIFT` | library alias string |
| `CATALOG_UNRESOLVED_REF` | the missing **`version.ref` name** from the library entry (for example `does-not-exist`), **never** the library alias |
| `PROJECT_REPO_FORBIDDEN` | exactly `repositories_mode` (the offline-vault.toml field name, **not** the kind string) |
| `OFFLINE_REPO_MISCONFIG` | exactly `vault_path` (the field name, **not** the kind string) |
| `PUBLISH_UNSIGNED` | exactly `signed_publish` (the field name, **not** the kind string) |
| `UNKNOWN_DEPENDENCY` | unknown dependency module id |
| `SELF_DEPENDENCY` / `DEPENDENCY_FANOUT` / `MODULE_CYCLE` | the module id |
| `BOM_OVERRIDE_FORBIDDEN` | first override coordinate in sorted order |
| `DUPLICATE_MODULE_COORDINATE` | `group:artifact` coordinate |
| `LOCK_VERSION_DRIFT` / `ORPHAN_LOCK_ENTRY` | lock coordinate |
| `LOCK_MISSING` | module id |

## Catalog defaults

`/app/meshgrid/catalog/libs.versions.toml` supplies:

- `[versions]` map of version name to version string
- `[libraries]` map of alias to `{ module = "group:artifact", version.ref = "name" }` or inline `version`
- `[bundles]` map of alias to library alias lists
- `[plugins]` map of plugin alias to `{ id = "...", version.ref = "..." }`

## policy_overrides

Optional object on `/app/meshgrid/workspace.manifest.json`. When a key is present, assign its value directly; do not invert booleans or rescale integers.

| Key | Type | Effect |
|-----|------|--------|
| `require_offline_vault` | bool | When false, skip `OFFLINE_REPO_MISCONFIG` |
| `fail_on_project_repos` | bool | When false, skip `PROJECT_REPO_FORBIDDEN` |
| `max_direct_deps` | int | Threshold for `DEPENDENCY_FANOUT` |
| `strict_bom` | bool | When false, skip `BOM_OVERRIDE_FORBIDDEN` |

## Plugin requests

`/app/meshgrid/plugins/plugin-requests.toml` lists `[[plugins]]` with `id`, `version`, and optional `min_gradle` as `major.minor`. A plugin is incompatible when requested Gradle (`gradle_major`.`gradle_minor` from the manifest) is strictly less than `min_gradle`. Compare numeric major then minor; never lexicographic string compare. Incompatible plugins emit `PLUGIN_INCOMPATIBLE` with `detail` equal to the plugin version string, `entity_id` equal to the plugin id, `module_id` `meshgrid`, and `event_seq` `0`.

## Module files

Each `/app/meshgrid/modules/{module_id}.module.json` has: `module_id`, `group`, `artifact`, `version`, `bom_consumer` (bool), `dependencies` (module ids), `library_aliases`, `version_overrides` (coordinate to version). Coordinate form is `group:artifact`.

Duplicate `group:artifact` across distinct module ids emits `DUPLICATE_MODULE_COORDINATE` on the later module (`entity_id` = coordinate, `detail` = earlier module id).

## Dependency rules

1. Unknown dependency module id → `UNKNOWN_DEPENDENCY` (`entity_id` = dependency id, `detail` = kind string `UNKNOWN_DEPENDENCY`)
2. Self dependency → `SELF_DEPENDENCY` (`entity_id` = module id, `detail` = empty)
3. Direct dependency count strictly greater than `max_direct_deps` (default 3) → `DEPENDENCY_FANOUT` (`entity_id` = module id, `detail` = decimal count)
4. After all modules, compute the set of modules that participate in at least one directed cycle (DFS / color or equivalent on the loaded dependency graph, ignoring edges to unknown modules). For each cyclic module, emit exactly one `MODULE_CYCLE` (`entity_id` = module id, `event_seq` = `max_ord + 1`). `detail` is the lexicographically smallest dependency id among that module's direct dependencies that are also in the cyclic set. If a module has multiple cyclic successors, pick the lex-smallest id only — never emit multiple cycle findings for one module.

## BOM rules

When `strict_bom` is true (default) and `bom_consumer` is true, any non-empty `version_overrides` emits `BOM_OVERRIDE_FORBIDDEN` (`entity_id` = first override coordinate in sorted order, `detail` = override version).

Emitting `BOM_OVERRIDE_FORBIDDEN` does **not** remove those overrides from lock cross-checks. The same coordinates still participate in `LOCK_VERSION_DRIFT` / `ORPHAN_LOCK_ENTRY` evaluation.

### Worked example: artifactseal BOM plus lock drift

Module `artifactseal` is a BOM consumer with override `com.google.guava:guava` = `32.0.0`, while its lock file records guava `33.0.0`. Emit **both** findings. They share module, entity, and ordinal, so uniqueness comes from the `kind` segment:

| kind | finding_id | detail |
|------|------------|--------|
| `BOM_OVERRIDE_FORBIDDEN` | `artifactseal::com.google.guava:guava::BOM_OVERRIDE_FORBIDDEN::0000` | `32.0.0` (override version) |
| `LOCK_VERSION_DRIFT` | `artifactseal::com.google.guava:guava::LOCK_VERSION_DRIFT::0000` | `33.0.0` (lock record version, never the override) |

Do not drop either finding. Do not change `finding_id` format to resolve the pair. `LOCK_VERSION_DRIFT.detail` is always the lock file version string.

## Referenced coordinates for lock cross-check

Build the expected coordinate→version map for a module as follows:

1. Resolve each `library_aliases` entry through the catalog (version.ref or inline version).
2. Then apply every `version_overrides` entry, which **overwrites** any catalog-resolved version for the same coordinate.

Overrides always win over catalog aliases for the same coordinate. A BOM consumer with forbidden overrides still uses the override versions when comparing non-optional lock records.

## Lock rules

See `LOCK_FORMAT.md`. Lock file path is `/app/meshgrid/locks/{module_id}.lock`.

## Offline publishing

See publish settings in `/app/meshgrid/publish/offline-vault.toml`.

All offline publish findings use `module_id` = `meshgrid` and `event_seq` = `0`.

`entity_id` is the **TOML field name**, never the finding `kind`:

| Condition | `kind` | `entity_id` | `detail` |
|-----------|--------|-------------|----------|
| `fail_on_project_repos` true and `repositories_mode` is not `FAIL_ON_PROJECT_REPOS` | `PROJECT_REPO_FORBIDDEN` | `repositories_mode` | current `repositories_mode` value |
| `require_offline_vault` true and `vault_path` is not `/app/meshgrid/offline-vault` | `OFFLINE_REPO_MISCONFIG` | `vault_path` | current `vault_path` value |
| `require_offline_vault` true and `signed_publish` is not true | `PUBLISH_UNSIGNED` | `signed_publish` | empty string |

Example: a wrong vault path yields `finding_id` `meshgrid::vault_path::OFFLINE_REPO_MISCONFIG::0000`, not `meshgrid::OFFLINE_REPO_MISCONFIG::OFFLINE_REPO_MISCONFIG::0000`.

## Post-mesh checks (`max_ord + 1`)

Emit at `event_seq = max_ord + 1` after all manifest entries are processed. `max_ord` is the maximum zero-based ordinal among all manifest entries including skipped duplicates.

**MODULE_CYCLE** — as in dependency rules; `module_id` and `entity_id` are the cyclic module id.

**CATALOG_UNRESOLVED_REF** — any library `version.ref` whose name is missing from `[versions]`: one finding per missing ref name. `module_id` = `meshgrid`. `entity_id` = the missing **ref name** (the string after `version.ref =`, for example `does-not-exist`). Do **not** use the library alias (for example `missing-ref`) as `entity_id`. `detail` = empty. Sort these findings by `entity_id` before merging into the global finding sort by `finding_id`.

## status

`STABLE` when `findings` is empty; otherwise `DRIFT`. Use exactly these two strings.
