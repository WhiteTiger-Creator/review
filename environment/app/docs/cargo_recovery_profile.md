# Bounded Cargo-inspired offline dependency recovery profile

This document is the normative behavior contract for `msrv-lock-recovery-planner`.
It is a **bounded Cargo-inspired offline dependency recovery profile**. It does
not claim to reproduce every current Cargo implementation detail.

Conceptual grounding (see `/app/source_snapshots/README.md`):

- greatest compatible version preference, with valid lock priority
- `allow` / `fallback` incompatible-Rust-version modes
- yanked ignored for new resolution unless locked
- root-only `[patch]` overlays
- equivalent source replacement by identical checksum

## Versions

Package versions and `rust_version` values are exactly `N.N.N` with unsigned
decimal integer components. Compare left to right as integers. Malformed values
are fatal during top-level input validation.

## Requirements

Only `=N.N.N` and `^N.N.N` are supported.

- Exact: matches one version.
- Caret upper bounds:
  - `^M.m.p` with `M > 0`: `>= M.m.p` and `< (M+1).0.0`
  - `^0.m.p` with `m > 0`: `>= 0.m.p` and `< 0.(m+1).0`
  - `^0.0.p`: `>= 0.0.p` and `< 0.0.(p+1)`

No prereleases, build metadata, ranges, wildcards, inequalities, or unions.

## Per-request resolution

1. Select requested workspace members by `member_id`.
2. Request MSRV = numerically smallest `rust_version` among those members.
3. Seed active requirements from every selected member’s direct dependencies.
4. Apply the selected root patch set as an overlay on its declared source.
5. For each package name, collect every active requirement.
6. Build the candidate set that satisfies every active requirement.
7. Exclude yanked candidates unless the exact package identity is reusable from
   the selected prior lock (same name, version, and lock-eligible identity).
8. If the prior locked candidate remains valid for the active requirements and
   yank rules, prefer it.
9. Otherwise apply the workspace `resolver_mode` (`allow` or `fallback`).
10. Load dependencies of the selected candidate into the active requirement set.
11. Repeat until a fixed point (no selection changes).
12. Reject with `package_version_conflict` when no candidate satisfies every
    active requirement for a name.
13. Reject with `resolution_round_limit` when rounds exceed
    `policy.maximum_resolution_rounds`.
14. Physical input ordering must not affect selection.

### `allow` mode

Select the numerically greatest valid candidate regardless of `rust_version`.

### `fallback` mode

1. Partition valid candidates by whether `rust_version <= request MSRV`.
2. If any compatible candidate exists, select the numerically greatest compatible
   candidate.
3. Otherwise select the numerically greatest valid candidate.

An exact requirement may therefore select an MSRV-incompatible package when no
compatible version matches.

## Root-only patches

Only the selected named patch set applies. Patched records must exist, match
`package_name`, and declare `patched_source_id` equal to the patch entry’s
`source_id`. A patched record with the same package name and version replaces
the original source record for candidate construction. Two patch entries that
target the same source, package name, and version are a `patch_conflict`.
Valid but unselected patches are projected as `unused`. Dependency-level patch
declarations do not exist in this profile.

## Equivalent source replacement

For every selected registry package whose original `source_id` has a mapping in
the selected replacement set:

1. Find the exact name and version under the replacement source.
2. Require identical checksum.
3. Project status `equivalent`, `missing`, or `checksum_mismatch`.
4. On `missing` or `checksum_mismatch`, reject the request (see precedence).
5. Replacement does not change version selection; it only rewrites the reported
   source reference for equivalent mirrors.
6. A replacement source cannot introduce a selected package absent from the
   original source.

## Lock-entry reuse

A prior lock entry for package `P` is reusable only when all are true:

- workspace digest matches
- selected patch-set digest matches
- selected replacement-set digest matches
- package version remains selected
- source kind and source reference match
- source digest and checksum match
- recorded direct dependency names match the selected package metadata
  (order-insensitive set equality)
- every direct dependency of `P` is itself reusable

Unrelated unselected registry mutations must not invalidate lock entries.

A patch mutation affects only the patched package and packages that depend on
its selected output through the resolved graph.

A replacement-source record mutation affects only selected packages mapped to
that replacement and their reverse dependents.

## Lockfile modes

### `frozen`

If any required selected lock entry is stale or missing: reject with
`lockfile_stale`. Do not recompute.

### `update`

Recompute every stale or missing selected entry and every selected reverse
dependent of a recomputed package. Reuse every independently valid entry.
Accept when resolution and source validation otherwise succeed.

## Request-level failure precedence

Evaluate in this exact order and stop at the first failure:

1. `unknown_member`
2. `unknown_lock`
3. `unknown_patch_set`
4. `unknown_replacement_set`
5. `patch_conflict`
6. `package_version_conflict`
7. `resolution_round_limit`
8. `source_replacement_missing`
9. `source_replacement_mismatch`
10. `lockfile_stale`

A structurally valid dataset with rejected requests still exits zero and emits
all request rows.

## Whole-run fatal conditions

Missing required files, unreadable JSON/NDJSON, wrong top-level JSON types,
duplicate global IDs, malformed versions/requirements/rust-versions/SHA-256
values, unknown cross-file identities that make the dataset structurally
invalid, policy limit exceeded, or duplicate `request_id` are fatal:

- remove stale requested output before processing
- exit nonzero
- write nonempty stderr
- leave no temporary output sibling

## Digests

All digests are SHA-256 over canonical JSON:

- UTF-8
- object keys sorted lexicographically
- arrays preserve declared semantic order unless defined as sets
- no insignificant whitespace
- lowercase hex digest

See `/app/docs/input_schema.md` for exact digest field sets.
