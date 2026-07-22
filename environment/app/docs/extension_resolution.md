# Extension resolution

Extension planning unions local extension requests with
`required_extensions` from the database policy fragment, then closes catalogue
dependencies before settings coupling and operation DAG construction.

## Dependency graph

Catalogue `requires` defines directed edges **required → dependent**. Example:
`cube` → `earthdistance` because `earthdistance.requires` contains `cube`.

Edges are per `(database_id, extension_id)` pair. Dependencies are resolved
inside each database independently.

## Closure algorithm

1. Start from the union of local and policy-required requests keyed by
   `(database_id, extension_id)`.
2. If the same key appears twice with different `version` values →
   `extension_version_conflict`.
3. For each present extension, recursively inject missing `requires`
   dependencies on the same `database_id`.
4. Injected dependency version is the sole entry in
   `allowed_versions` when that list has length 1; otherwise →
   `extension_dependency_missing`.
5. Unknown `extension_id` → `unknown_extension`.
6. After closure, run a cycle check on the extension-ID graph induced by
   catalogue `requires` among selected extensions. A cycle →
   `extension_dependency_cycle`.

## Selection reasons

Each extension row carries `selection_reason`:

| Value | Meaning |
|---|---|
| `local` | Request originated in cluster YAML |
| `policy_required` | Request originated in `required_extensions` |
| `merged` | Same semantic request from both sources (identical version) |
| `dependency` | Injected by closure; not present in local or policy input |

Injected dependency rows use `extension_request_id` of the form
`dep_<database_id>_<extension_id>`.

## Dependency depth

`dependency_depth` is computed per extension ID in the catalogue:

- `0` when `requires` is empty
- otherwise `1 + max(depth(dep) for dep in requires)`

Depth is independent of `database_id`; the same extension ID shares one depth
value within a cluster plan.

## Topological ordering

After closure, order extensions for output rows and `create_extension`
operations:

1. Group by `database_id` ascending UTF-8.
2. Within each database, sort by:
   - `dependency_depth` ascending
   - `extension_id` ascending UTF-8
   - `version` ascending UTF-8
   - `extension_request_id` ascending UTF-8
3. Assign `topological_position` as 0-based positions in that final sequence
   across all databases (production order: all extensions for the first
   database, then the next database, and so on).

Global cycle detection uses Kahn topological sort over extension IDs with
ready-set tie-break: `extension_id` ascending UTF-8. A dependency extension
precedes its dependent in both the global sort and per-database operation
dependencies.

## Extension-setting coupling

After settings resolve, verify each selected extension's catalogue
`required_settings` against normalized settings. Failure →
`required_extension_setting_unsatisfied`. Do not inject extension-required
settings unless also marked required by organization setting policy.

## Extension rows

Emit `extension_rows` with: `cluster_id`, `database_id`, `extension_id`,
`version`, `selection_reason`, `dependency_depth`, `topological_position`.
Sort by `cluster_id`, `database_id`, `topological_position`, `extension_id`.
