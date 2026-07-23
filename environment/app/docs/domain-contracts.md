# Domain Contracts

This document is the public contract for exit codes, dataset identity, validation issue codes, registry digests, and structured report fields.

## Exit codes

| Exit | Meaning                                | Report behavior                                             |
| ---- | -------------------------------------- | ----------------------------------------------------------- |
| `0`  | Successful audit or playthrough        | Publish the completed canonical report                      |
| `1`  | Operational failure                    | Do not publish a completed content-validation report        |
| `2`  | Content or gameplay validation failure | Publish the completed structured report showing the failure |

### Content failures (exit `2`)

Content failures include:

- JSON Schema violations
- dataset missing-ID errors (`dataset.missing-id`)
- dataset ambiguous-ID errors (`dataset.ambiguous-id`)
- legacy fingerprint mismatches (`dataset.fingerprint-mismatch`)
- graph reference errors
- default-route cycles
- default-route dead ends
- a validly executed playthrough that cannot reach the configured exit

Question-ID and fingerprint failures are content violations and therefore return `2`, not `0` or `1`.

### Operational failures (exit `1`)

Operational failures include:

- missing or unreadable dataset
- missing or unreadable contracts directory
- malformed TOML that prevents configuration loading
- unwritable output or state destination
- missing required audited state for playthrough
- corrupt operational input that prevents validation from running

## Issue tuples

Audit failures are reported as tuples `(artifact, pointer, code)` where:

- `artifact` is a root-relative POSIX path (for example `bundle/nodes/legacy-enc.yaml`).
- `pointer` is an RFC 6901 JSON Pointer (for example `/trivia/row`, `/encounters`, `/subtitle`).
- `code` is a stable machine identifier listed below.

Audit collects **all** schema, dataset, and graph findings across every loaded manifest before reporting. Independent defects in different files must all appear in the final issue list; validation must not stop after the first error.

Schema validation is data-driven: each artifact kind maps to a JSON Schema file in the contracts directory. Map validator output to the stable `schema.*` codes below (for example `schema.required`, `schema.type`); do **not** emit raw numeric library codes.

Graph issues are attributed to the manifest file where the defect appears (room or encounter YAML), not to dungeon configuration TOML. Cycle and dead-end issues typically use pointer `/exits` on the trapping room file.

Issues are sorted lexicographically by `(artifact, pointer, code)`.

### Schema codes

| Code | Meaning |
|------|---------|
| `schema.required` | Required property missing at `pointer` |
| `schema.type` | Value type does not match schema |
| `schema.enum` | Value not in allowed enumeration |
| `schema.additionalProperties` | Unknown property present |

### Dataset codes

| Code | Meaning |
|------|---------|
| `dataset.missing-id` | Stable `question_id` or legacy row has no matching row |
| `dataset.ambiguous-id` | Stable `question_id` matches more than one row |
| `dataset.fingerprint-mismatch` | Legacy row index matches canonical order but `question_sha256` does not match the question text |

Stable `question_id` resolution queries the full dataset for the exact ID. Zero matches produce `pointer: /trivia/question_id`, `code: dataset.missing-id`. Exactly one match resolves successfully. More than one match produces `pointer: /trivia/question_id`, `code: dataset.ambiguous-id`. When the count is greater than one, do not select the first matching row, do not add an ambiguous encounter to the valid registry, continue validating other artifacts, and return exit `2`. SQL `LIMIT 1` or first-row selection does not satisfy the uniqueness contract.

### Graph codes

| Code | Meaning |
|------|---------|
| `graph.duplicate-encounter` | Room lists the same encounter twice |
| `graph.missing-encounter` | Room references an encounter id that was not loaded |
| `graph.unknown-room` | Exit or encounter references an unknown room |
| `graph.cycle` | Following default exits from the start room revisits a room before reaching the configured exit |
| `graph.dead-end` | Default exit path terminates in a room that cannot reach the configured exit |

## Dynamic dungeon roots

No bundled room or encounter ID is hardcoded into validation.

The effective `start_room` and `exit_room` come from the effective configuration. Generated dungeon roots may use names such as `entry`, `middle`, and `exit`, or entirely different valid IDs. Aliases are resolved when looking up the start room, exit targets, room transitions, and encounter room references.

Graph validation operates only on the manifests loaded from the effective content directory. An existing effective start room must not be rejected merely because it differs from the bundled `foyer`. An existing effective exit room must not be rejected merely because it differs from the bundled `vault`.

Validation responsibilities:

- every room encounter reference must resolve to a loaded encounter
- duplicate encounter IDs within one room are reported
- every room exit target must resolve to a loaded room after alias resolution
- every encounter's `room` must resolve to a loaded room
- cycle and dead-end checks follow `default` exits starting at the effective start room
- reaching the effective exit room completes the route
- do not require every unrelated room in the registry to be reachable from the start

Graph issues must remain attributed to the manifest containing the bad reference.

## Canonical legacy row order

Legacy `row` is **1-based**. Dataset rows are ordered by `question_id ASC`. Physical Parquet storage order is irrelevant.

Resolution steps:

1. Resolve the logical row first.
2. Compute the canonical fingerprint from that row's question text.
3. Compare the complete lowercase hexadecimal SHA-256 value.

Outcomes:

- An out-of-range row produces `pointer: /trivia/row`, `code: dataset.missing-id`.
- A row that exists but has a different fingerprint produces `pointer: /trivia/question_sha256`, `code: dataset.fingerprint-mismatch`.
- A fingerprint mismatch must not return the row as a valid resolved question.
- A stale fingerprint is a content violation and returns exit `2`.

## Question fingerprint (SHA-256)

The canonical `question_sha256` for legacy locators is:

1. NFC Unicode normalization
2. Per-code-point Unicode simple lowercase (Java `Character.toLowerCase` on each code point). This is **not** Python `str.casefold()` and **not** `String.toLowerCase(Locale.ROOT)`; those full mappings differ on characters such as `İ` (U+0130).
3. Remove characters that are not letters, digits, or whitespace (Unicode-aware)
4. Collapse whitespace and trim
5. **SHA-256** hex digest of the UTF-8 bytes

Answer and alias matching uses the same normalization pipeline as documented in `manifest-format.md`.

## Registry digest (SHA-256)

Room IDs and encounter IDs are stored and iterated in lexicographic order.

The registry digest payload is exactly:

```json
{"encounters":["..."],"rooms":["..."]}
```

Object keys are ordered `encounters`, then `rooms`. Each array is sorted lexicographically by ID. Discovery order, filesystem order, hash-map order, CWD, and Parquet physical order must not affect the digest.

Audit and playthrough compute or validate the same digest from the same audited registry snapshot. Playthrough must load the successful audited registry snapshot. It must not independently reparse current manifests when an authoritative audited state is required.

## Input digest and state

`input_digest` covers the state format version, effective root, dataset path, contracts path, start/exit rooms, content hashes of every selected manifest and contract file, and a **SHA-256** of the raw dataset bytes. Reusable state is valid only when this digest matches; failed or truncated state must not be treated as success. See `state-notes.md` for the full preimage definition.

### Digest path normalization (CWD)

Before hashing path components into `input_digest`, normalize these values with absolute, CWD-independent forms (`Path.toAbsolutePath().normalize()` or equivalent):

- effective root
- effective dataset path
- effective contracts path

Manifest entries in the digest preimage use root-relative POSIX paths derived after normalizing both the root and the file path (never the process CWD). Contract entries use the schema filename only. Raw dataset bytes are hashed directly; do not include a CWD-relative dataset path string as a substitute for those bytes.

## Deterministic reports

Reports must be byte-reproducible across cold and warm executions with equivalent inputs.

Requirements:

- UTF-8 encoding
- lexicographically sorted object keys at every nesting level
- exactly one trailing LF
- issues sorted by `(artifact, pointer, code)`
- room and encounter identity arrays in deterministic order
- root-relative POSIX paths in the fields listed under Output contract summary
- no `/tmp` paths
- no CWD-dependent paths
- no timestamps or cache-hit markers
- no random identifiers

Cold and warm executions with equivalent inputs must produce byte-identical `audit-report.json` and `playthrough.json`. Using a different process CWD must not alter those bytes.

## Output contract summary

This section consolidates the load-bearing report rules. Prefer it over piecing requirements from other docs.

### Root-relative path fields

These report values must be root-relative POSIX paths (no leading `/`, no `\\`, no absolute or CWD-dependent forms):

- `audit-report.json` → `issues[].artifact`
- `audit-report.json` → each path entry in `artifacts` (manifest paths such as `bundle/nodes/….yaml`)

These are **not** path fields (hex digests or booleans/ints): `input_digest`, `registry_digest`, `success`, `issue_count`, `pointer`, `code`, `message`, and playthrough score/route fields.

### `dataset_digest` calculation

`dataset_digest` is the lowercase hex **SHA-256** of the raw Parquet file bytes (64 hex characters, no `sha256:` prefix, no path). It is an identity calculation, not a top-level audit-report field.

The published `audit-report.json` object includes exactly **6** schema keys: `artifacts`, `input_digest`, `issue_count`, `issues`, `registry_digest`, and `success`.

On successful audit, embed that digest as one string element inside the `artifacts` array alongside root-relative manifest paths, then sort the whole array lexicographically. On unsuccessful audits, do not require the digest entry.

Inverse check: recomputing SHA-256 of the effective dataset bytes must equal the hex string found in `artifacts`.

### `audit-report.json`

Exactly **6** top-level schema keys: `artifacts`, `input_digest`, `issue_count`, `issues`, `registry_digest`, `success`.

Each issue object contains `artifact`, `pointer`, `code`, and `message`.

### `playthrough.json`

Required top-level fields: `encounters`, `reached_exit`, `registry_digest`, `total_score`, `visited_rooms`.

`registry_digest` must equal the audited registry digest. `visited_rooms` and `encounters` list ids in visit order. `reached_exit` is **true** only when the configured exit room is reached; otherwise **false**. `total_score` is an integer sum of encounter scoring using the streak and difficulty rules in `manifest-format.md` (`streak >= threshold`; difficulty tiers by ascending `min`, last match wins).

### Boolean polarity

| Field | true | false |
|-------|------|-------|
| `audit-report.json` → `success` | zero issues after validation | any schema, dataset, or graph issue |
| `playthrough.json` → `reached_exit` | exit room reached | cycle, dead end, or missing room |

Reports must not embed absolute `/tmp/` paths in artifact fields.

## Reproducibility roots and identity helpers

Physical reorder and alternate-root comparisons may refer to a primary dataset/contracts pair and a secondary pair labeled `dataset_b` and `contracts_b`. The `dataset_digest` for each root is the SHA-256 of that root's raw Parquet bytes. Shared identity helpers document fingerprint and digest formulas used when comparing those roots; they do not change the published CLI contract.

Schema-variant probes may add a `probe` property to copied contract files. Agents are not required to author those filenames in bundled content.

JSON Pointer probes may reference `/streaks/bonuses/0/threshold`. Scenario tags such as `cli/env/toml precedence` name generated cases only. Internal helper fields include `keyword_room_ids`, `passing_encounter`, and `resolved_question`.

## Illustrative content and path labels

Illustrative dungeon roots and scratch path segments may use labels such as: `00-a.yaml`, `00-entry.yaml`, `00-trap.yaml`, `01-b.yaml`, `01-broken.yaml`, `01-exit.yaml`, `01-middle.yaml`, `bad-streaks.yaml`, `blocked`, `contracts_a`, `contracts_b`, `dataset.parquet`, `datasets`, `enc-entry.yaml`, `enc-middle.yaml`, `fixture_hashes.json`, `hash-check.json`, `keywords.yaml`, `legacy.yaml`, `matching.yaml`, `missing.parquet`, `nested`, `nonmatching.yaml`, `not-a-dir`, `off-room.yaml`, `operational-out`, `operational-state.json`, `out-a`, `out-b`, `out-c`, `probe.yaml`, `stale.yaml`, `state-a.json`, `state-b.json`, `test-bundled`, `trivia-dungeon-1.0.0-SNAPSHOT.jar`, and `uni-enc.yaml`.

Full root-relative paths include `bundle/chambers/00-a.yaml`, `bundle/chambers/00-trap.yaml`, `bundle/chambers/01-broken.yaml`, `bundle/nodes/duplicate.yaml`, `bundle/nodes/missing.yaml`, `bundle/nodes/nonmatching.yaml`, `bundle/nodes/stale.yaml`, and `bundle/weights/bad-streaks.yaml`.

Generated dungeon smoke content may use encounter ids such as `enc-entry` and `enc-middle`. Agents are not required to author these illustrative paths in bundled content.
