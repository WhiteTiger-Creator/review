# Report schema

Write `/app/output/report.json` (or `--output`) atomically. Top-level keys must
appear in this exact order:

1. `request_rows`
2. `package_selection_rows`
3. `patch_rows`
4. `source_replacement_rows`
5. `lock_entry_rows`
6. `invalidation_rows`
7. `conflict_rows`
8. `summary`

## Sorting

| Family | Sort keys |
| --- | --- |
| `request_rows` | `request_id` |
| `package_selection_rows` | `request_id`, `package_name` |
| `patch_rows` | `request_id`, `source_id`, `package_name`, `patched_version` |
| `source_replacement_rows` | `request_id`, `original_source_id`, `package_name`, `version` |
| `lock_entry_rows` | `request_id`, `package_name` |
| `invalidation_rows` | `request_id`, `package_name`, `cause_kind`, `cause_subject` |
| `conflict_rows` | `request_id`, `conflict_type`, `subject`, `reason_code` |

String arrays are sorted lexicographically unless noted as ordered sequences.

Emit detail rows only for accepted requests, except:

- `request_rows`: one row per request (accepted or rejected)
- `conflict_rows`: one row for each request-level rejection
- `patch_rows`: for rejected requests, still emit patch projection rows when the
  patch set was resolved far enough to evaluate patches (after unknown_* checks
  pass). If rejection occurs at `unknown_patch_set` or earlier, emit no patch
  rows for that request.
- `source_replacement_rows` / `lock_entry_rows` / `invalidation_rows` /
  `package_selection_rows`: only for accepted requests

On `lockfile_stale` (frozen): emit no package/lock/invalidation/replacement
detail rows for that request; emit a conflict row; patch rows may still be
emitted if patches were evaluated before the lock check.

## `request_rows`

| Field | Type |
| --- | --- |
| `request_id` | string |
| `lockfile_mode` | `frozen` \| `update` |
| `resolver_mode` | `allow` \| `fallback` |
| `request_msrv` | string or null | null when rejected before members resolve |
| `status` | `accepted` \| `rejected` |
| `reason_or_null` | string or null | rejection token or null |
| `selected_package_count` | integer |
| `reused_lock_entry_count` | integer |
| `recomputed_lock_entry_count` | integer |

## `package_selection_rows`

| Field | Type |
| --- | --- |
| `request_id` | string |
| `package_name` | string |
| `selected_version` | string |
| `selection_source` | `registry` \| `patched_path` \| `patched_git_snapshot` \| `replacement_registry` |
| `source_reference` | string |
| `source_digest` | string |
| `checksum` | string |
| `rust_version` | string |
| `msrv_compatible` | bool |
| `yanked` | bool |
| `locked_version_or_null` | string or null |
| `lock_status` | `reused` \| `recomputed` \| `stale_rejected` |

## `patch_rows`

One row per patch entry in the selected patch set.

| Field | Type |
| --- | --- |
| `request_id` | string |
| `source_id` | string |
| `package_name` | string |
| `patched_package_id` | string |
| `patched_version` | string |
| `status` | `selected` \| `unused` \| `rejected` |
| `reason_or_null` | string or null | `package_mismatch`, `source_mismatch`, `duplicate_target`, or null |

## `source_replacement_rows`

One row per selected package whose original registry `source_id` has a
replacement mapping.

| Field | Type |
| --- | --- |
| `request_id` | string |
| `package_name` | string |
| `version` | string |
| `original_source_id` | string |
| `replacement_source_id` | string |
| `original_checksum` | string |
| `replacement_checksum_or_null` | string or null |
| `status` | `equivalent` \| `missing` \| `checksum_mismatch` |

## `lock_entry_rows`

One row per package present in the prior lock **or** newly selected.

| Field | Type |
| --- | --- |
| `request_id` | string |
| `package_name` | string |
| `prior_digest_or_null` | string or null |
| `computed_digest` | string | empty string when not selected and no computation |
| `status` | `reused` \| `recomputed` \| `stale_rejected` \| `not_selected` |
| `reason_or_null` | string or null | `digest_mismatch`, `missing_lock_entry`, `upstream_invalidated`, or null |

## `invalidation_rows`

Emitted for each package that is not reused while selected (or required but
stale under frozen). 

| Field | Type |
| --- | --- |
| `request_id` | string |
| `package_name` | string |
| `cause_kind` | `selection_changed` \| `source_changed` \| `dependency_changed` \| `missing_lock_entry` \| `upstream_invalidated` |
| `cause_subject` | string | for `upstream_invalidated` rows, the name of the upstream package that caused the invalidation (not the invalidated package's own name) |
| `dependent_packages` | string array | sorted unique reverse dependents that must recompute |

## `conflict_rows`

| Field | Type |
| --- | --- |
| `request_id` | string |
| `conflict_type` | string | equals `reason_code` family token |
| `subject` | string |
| `reason_code` | same tokens as request rejection reasons |
| `related_values` | string array | sorted unique; no free-form prose |

## `summary`

Derived only from emitted rows:

| Field | Derivation |
| --- | --- |
| `request_count` | len(request_rows) |
| `accepted_request_count` | count status=accepted |
| `rejected_request_count` | count status=rejected |
| `package_selection_row_count` | len(package_selection_rows) |
| `selected_patch_count` | count patch_rows status=selected |
| `replacement_row_count` | len(source_replacement_rows) |
| `reused_lock_entry_count` | count lock_entry_rows status=reused |
| `recomputed_lock_entry_count` | count lock_entry_rows status=recomputed |
| `conflict_count` | len(conflict_rows) |
