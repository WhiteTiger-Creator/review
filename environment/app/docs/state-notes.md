# Audit State

Reusable audit state avoids redundant work when inputs are unchanged. State is stored as JSON at the path given by `--state`.

## Content-addressed identity

### Input-digest preimage

The `input_digest` must cover, in deterministic lexicographic order:

- state format version `"1"`
- normalized effective root path
- normalized effective dataset path
- normalized effective contracts path
- effective `start_room`
- effective `exit_room`
- each selected manifest's root-relative POSIX path and SHA-256 content digest
- each selected JSON Schema filename and SHA-256 content digest
- SHA-256 of the raw Parquet dataset bytes

The digest must **not** depend on:

- file modification time
- file size as a substitute for content
- inode
- directory iteration order
- output directory
- state-file path
- process CWD
- cache-hit status
- report timestamps
- temporary file names
- data already stored in the state file

Changing manifest, contract, or dataset bytes invalidates state even when the path, size, and mtime remain unchanged.

Changing only mtime without changing bytes does not invalidate state.

## Cache acceptance

A cached state may be reused only when:

- the state file is complete valid JSON
- `success` is exactly `true`
- `input_digest` equals the freshly recomputed digest
- a registry snapshot exists and is deserializable

The following are cache misses, not reusable success:

- truncated JSON
- malformed JSON
- missing registry
- `success: false`
- absent digest
- mismatched digest
- a partially written temporary file

On a cache miss, perform a full audit.

## Atomic publication

Publication rules:

1. Never write reusable success state before all validation succeeds.
2. Content failures and operational failures must not replace a previous successful state.
3. Serialize successful state to a sibling temporary file.
4. Finish writing the complete document.
5. Atomically replace the final state file.
6. A failed or interrupted write must not leave a reusable final state.

| Run outcome | State file |
|-------------|------------|
| Success (exit 0) | Updated atomically with new digest and registry |
| Content violations (exit 2) | Unchanged; no partial success header |
| Operational failure (exit 1) | Unchanged |

## Registry snapshot

On successful audit, state stores a canonical registry snapshot (rooms, encounters, resolved questions, aliases, scoring). Playthrough loads this snapshot rather than re-parsing manifests independently.

Warm runs with matching `input_digest` skip re-validation and reuse the stored registry.

## Report outputs

`audit-report.json` includes the `input_digest`, issue list, artifact summary, and registry digest. Reports use canonical JSON: lexicographically sorted object keys, deterministic array ordering, root-relative POSIX artifact paths, UTF-8 with a single trailing newline.
