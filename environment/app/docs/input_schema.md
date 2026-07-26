# Input schema

All paths are relative to `--data-dir` (default `/app/data`). Physical key order
in JSON files is irrelevant. Duplicate global IDs are fatal.

## Required files

| File | Top-level type |
| --- | --- |
| `workspace.json` | object |
| `registry_packages.json` | array |
| `patched_packages.json` | array |
| `patch_sets.json` | array |
| `replacement_sources.json` | array |
| `previous_locks.json` | array |
| `build_requests.ndjson` | NDJSON object rows |
| `policy.json` | object |

## `workspace.json`

| Field | Type | Notes |
| --- | --- | --- |
| `workspace_name` | string | non-empty |
| `resolver_mode` | string | `allow` or `fallback` |
| `members` | array | unique `member_id` |

Each member:

| Field | Type |
| --- | --- |
| `member_id` | string |
| `package_name` | string |
| `package_version` | `N.N.N` |
| `rust_version` | `N.N.N` |
| `dependencies` | array |

Each dependency:

| Field | Type |
| --- | --- |
| `package_name` | string |
| `source_id` | string |
| `requirement` | `=N.N.N` or `^N.N.N` |

Member dependency arrays are unordered sets keyed by `package_name` (duplicate
`package_name` within one member is fatal).

## `registry_packages.json`

Each record:

| Field | Type |
| --- | --- |
| `package_name` | string |
| `version` | `N.N.N` |
| `source_id` | string |
| `checksum` | 64 lowercase hex |
| `rust_version` | `N.N.N` |
| `yanked` | bool |
| `dependencies` | array of `{package_name, source_id, requirement}` |

Identity: `(source_id, package_name, version)` must be unique.

## `patched_packages.json`

| Field | Type |
| --- | --- |
| `patched_package_id` | string | unique |
| `package_name` | string |
| `version` | `N.N.N` |
| `patched_source_id` | string |
| `source_kind` | `path_snapshot` or `git_snapshot` |
| `source_reference` | string |
| `source_digest` | 64 lowercase hex |
| `rust_version` | `N.N.N` |
| `dependencies` | array |

## `patch_sets.json`

| Field | Type |
| --- | --- |
| `patch_set_id` | string | unique |
| `patches` | array |

Each patch:

| Field | Type |
| --- | --- |
| `source_id` | string |
| `package_name` | string |
| `patched_package_id` | string | must exist in `patched_packages.json` |

## `replacement_sources.json`

| Field | Type |
| --- | --- |
| `replacement_set_id` | string | unique |
| `mappings` | array |
| `replacement_records` | array |

Each mapping: `{original_source_id, replacement_source_id}` — unique
`original_source_id` within a set.

Each replacement record:

| Field | Type |
| --- | --- |
| `replacement_source_id` | string |
| `package_name` | string |
| `version` | `N.N.N` |
| `checksum` | 64 lowercase hex |
| `source_reference` | string |

Identity within a set: `(replacement_source_id, package_name, version)`.

## `previous_locks.json`

| Field | Type |
| --- | --- |
| `lock_id` | string | unique |
| `workspace_digest` | 64 lowercase hex |
| `patch_set_digest` | 64 lowercase hex |
| `replacement_set_digest` | 64 lowercase hex |
| `selected_packages` | array |

Each selected package:

| Field | Type |
| --- | --- |
| `package_name` | string | unique within lock |
| `version` | `N.N.N` |
| `source_kind` | `registry`, `patched_path`, `patched_git_snapshot`, or `replacement_registry` |
| `source_reference` | string |
| `source_digest` | 64 lowercase hex |
| `checksum` | 64 lowercase hex |
| `dependency_names` | string array | treated as a set |

## `build_requests.ndjson`

One JSON object per line. Physical row order is irrelevant. Duplicate
`request_id` is fatal.

| Field | Type |
| --- | --- |
| `request_id` | string |
| `lock_id` | string |
| `patch_set_id` | string |
| `replacement_set_id` | string |
| `lockfile_mode` | `frozen` or `update` |
| `member_ids` | string array | unique ids; order irrelevant |

## `policy.json`

| Field | Type | Constraint |
| --- | --- | --- |
| `maximum_packages` | integer | >= 1 |
| `maximum_dependency_edges` | integer | >= 1 |
| `maximum_resolution_rounds` | integer | >= 1 |
| `maximum_requests` | integer | >= 1 |
| `maximum_workspace_members_per_request` | integer | >= 1 |

Exceeding a limit after structural parse is fatal.

## Digest field sets

Canonical JSON rules: UTF-8, lexicographically sorted object keys, no
insignificant whitespace, arrays keep the order defined below, lowercase hex.

### Workspace digest

Canonical object:

```json
{
  "members": [ /* sorted by member_id; each member:
    { "dependencies": [sorted by package_name],
      "member_id", "package_name", "package_version", "rust_version" } */ ],
  "resolver_mode": "...",
  "workspace_name": "..."
}
```

Each dependency object keys: `package_name`, `requirement`, `source_id`.

### Patch-set digest

```json
{
  "patch_set_id": "...",
  "patches": [ /* sorted by (source_id, package_name, patched_package_id) */ ]
}
```

### Replacement-set digest

```json
{
  "mappings": [ /* sorted by original_source_id */ ],
  "replacement_records": [ /* sorted by
      (replacement_source_id, package_name, version) */ ],
  "replacement_set_id": "..."
}
```

### Registry source digest

For a registry package record after patch overlay selection:

```json
{
  "checksum": "...",
  "package_name": "...",
  "source_id": "...",
  "version": "..."
}
```

### Patched source digest

Use the `source_digest` field from the patched package record (already a digest).
When projecting selected patched packages, `source_digest` in the report equals
that field.

### Selected-package lock digest

```json
{
  "checksum": "...",
  "dependency_names": [ /* sorted unique */ ],
  "package_name": "...",
  "source_digest": "...",
  "source_kind": "...",
  "source_reference": "...",
  "version": "..."
}
```

### Computed dependency-closure digest

Identical algorithm to the selected-package lock digest for the package as
selected in the current resolution (including post-replacement projection when
status is `equivalent`).
