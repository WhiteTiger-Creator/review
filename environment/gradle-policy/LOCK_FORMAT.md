# Meshgrid LOCK1 dependency lock format (read-only)

Read this file together with /app/gradle-policy/REPORT_LAYOUT.md /app/gradle-policy/CATALOG_RULES.md and /app/gradle-policy/PLUGIN_COMPAT.md for all rules.

Per-module locks ship as UTF-8 text under /app/meshgrid/locks/{module_id}.lock.

## File layout

| Line | Field | Rule |
|------|-------|------|
| 1 | magic | exactly `LOCK1` |
| 2 | `format_version` | decimal integer must be `1` |
| 3 | `record_count` | decimal integer; number of coordinate lines that follow |
| 4+ | records | one per line |

## Record line

Tab-separated fields in order:

1. `coordinate` — `group:artifact`
2. `version` — non-empty version string
3. `checksum` — lowercase hex SHA-256 of UTF-8 bytes `{coordinate}|{version}` only. Do **not** fold the optional `0`/`1` field into the digest material.
4. `optional` — `0` or `1`

Shipped files under `/app/meshgrid/locks/` already use that digest. Do **not** rewrite lock files to match a different formula. The only intentional mismatch is deliberate `BAD_CHECKSUM` rows (for example `com.example:badcheck` with a non-matching checksum).

Worked example (matches cataloghub.lock): UTF-8 material `com.google.guava:guava|33.0.0` digests to `6c1e6756800922e84d874b39eeb4771c59ab72a493244978e5116427bd400ee5`. Digests that include `|0` or `|1` after the version are wrong for this task.

Process records in file order. Track every `coordinate` in a set. Duplicate coordinate lines emit lock counter `dup_coord_rejects` and are rejected.

Rejection reasons assigned in order: `BAD_OPTIONAL` when optional is not `0`/`1`, then `BAD_CHECKSUM` when checksum mismatches, then `DUP_COORD` when coordinate already seen.

`records_total` counts lines after the header that were attempted. `records_valid` counts accepted records. `records_rejected` counts rejected records. `payload_bytes` sums byte lengths of valid record lines excluding the trailing newline.

## Cross-check against module

For each valid lock coordinate that is not optional (`optional=0`):

- Build the module's referenced coordinate map per `CATALOG_RULES.md` (library aliases first, then `version_overrides` overwrite). BOM-forbidden overrides still count here.
- If the coordinate is in that map and versions differ → `LOCK_VERSION_DRIFT` (`entity_id` = coordinate, `detail` = **lock record version** string exactly as stored in the lock file; never the module override version).
- If checksum is wrong relative to lock version string, that record is already rejected at decode time; do not also emit `LOCK_VERSION_DRIFT` for rejected records.
- If the coordinate is not in the referenced map → `ORPHAN_LOCK_ENTRY` (`entity_id` = coordinate, `detail` = empty).

Missing required lock file for a listed module emits `LOCK_MISSING` (`entity_id` = module id, `detail` = empty) and skips lock decode counters for that module (`capture` zeros).

Optional lock entries (`optional=1`) never produce `LOCK_VERSION_DRIFT` or `ORPHAN_LOCK_ENTRY`.

## Capture block

Each module row includes `capture` with: `format_version`, `records_total`, `records_valid`, `records_rejected`, `dup_coord_rejects`, `payload_bytes`. When a lock file is present and valid, `format_version` is the JSON integer from LOCK1 header line 2 (must be `1`). It is **not** the magic string `LOCK1` and must not be emitted as a JSON string. When the lock file is missing, all capture integers are `0` including `format_version`.
