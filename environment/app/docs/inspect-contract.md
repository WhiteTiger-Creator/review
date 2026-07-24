# Inspect command contract

Binary `pixilock`. `pixilock --version` prints exactly `pixilock 12.6.3`.

## CLI flags (exact)

```
pixilock inspect \
  --lane <name> \
  --edges <path> --artifacts <path> --deps <path> \
  --mirrors <path> --pins <path> --xor <path> --bans <path> \
  --forbidden-hosts <path> --version-caps <path> \
  --risk-policy <path> --cascade-policy <path> --cascade-route-blocks <path> \
  --retention-hops <int> \
  --out <path>
```

`--out` is the path of the JSON file to write. Create missing parent directories before writing.

**`--lane` is always required and always meaningful**, including when CSV paths are absolute/temp files rather than a packaged bundle:
1. Echo `--lane` into the output JSON `lane` field (never leave `lane` empty).
2. Filter `edges` / `artifacts` / `deps` / `xor` / selected cascade policy & blocks to that lane before analysis.
3. Do **not** infer the lane from CSV path directories or filenames.

## Output schema (exact)

Top-level keys **exactly** (no extras): `lane`, `retention_hops`, `artifacts`, `totals`.

**`artifacts` MUST be sorted ascending by `coordinate`**. Each artifact object keys exactly:
`coordinate`, `status`, `holds`, `risk_score`.
`holds` is a list of **plain strings** (not objects).
`status` is `release` iff `holds` empty else `hold`.

Edges after lane filter: parent,child,edge_kind. Soft never conflicts/cascades.
When `retention_hops` is `0`, no cascades are emitted. Effective hops for a prefix are
`min(retention_hops, cascade-policy.max_hops)` for that lane+prefix.

Hold emission (per artifact):
If the same hold string is emitted more than once, keep one copy and take the **max** risk for that string.
Then `risk_score` for the artifact is the **sum** of those unique hold risks (not max-of-all holds).
`risk_score_total` is the sum of every artifact's `risk_score`.

## Risk policy

`risk-policy.csv` columns `kind,risk` are authoritative for local hold scores (kinds:
remote,hashdrift,versiondrift,mirrormiss,provcollide,xor,missingpin,ban,cap). Fail closed on
missing kinds, duplicates, non-positive risks, or wrong header. Do **not** hardcode risk numbers.

## Cascade routing (hard)

Only these local hold prefixes cascade: `ban:`, `remote:`, `xor:`, `provcollide:`, `cap:`.
**Do not cascade** `hashdrift:`, `versiondrift:`, `mirrormiss:`, or `missingpin:`.

Walk **reverse hard edges only**. Soft edges never participate.

`cascade-policy.csv` supplies per-lane per-prefix `decay` and `max_hops` (exactly one positive
decay row for each cascading prefix per matrix lane).

`cascade-route-blocks.csv` rows `(lane,prefix,block_match)`: parents whose coordinate starts with
`block_match` may be **cascade targets** but are never **expansion** nodes for that prefix.

For each cascading origin hold, pick the best reverse-hard route to each reachable ancestor within
the effective hop budget:

1. shorter hop distance `d` wins;
2. if `d` ties, lexicographically smaller **via** wins.

`via` is intermediates between origin and target (excluding both ends), joined with `/`.
If `d == 1`, `via` is exactly `-` (never the target or origin coordinate).

Emit one cascade per `(target, origin, original_hold)`:

- hold string: `cascade:<d>:<origin_coord>@<via>:<original_hold_string>`
- risk: `max(1, origin_hold_risk - decay * d)` using the prefix policy decay

Shipped edge blocks stop `spine:` expansion for ban/remote/xor/provcollide, so `svc:app` ban
cascades via `mid:alpha` (not spine). Cap blocks `mid:` expansion, so `svc:app` does not receive
cap via mid within the hop budget.

## Local holds

1. Remote URL: dep `source_url` **or** `patch_url` contains a forbidden host substring OR does not start with `file:///`:
   `remote:<coord>:<field>` field is `source` or `patch`, risk from risk-policy on the dep coordinate.
   Empty `patch_url` does **not** emit a remote hold. Non-empty remote patches always do.
2. Hash drift: pin sha256 for dep != dep source_hash after normalizing both sides (strip an optional leading `sha256:` for **comparison only**):
   `hashdrift:<coord>:<expected>:<actual>` (stripped hex in the hold string).
3. Version drift: pin version for dep != dep version string:
   `versiondrift:<coord>:<pin_version>:<dep_version>`
4. Mirror miss: emit `mirrormiss:<coord>:<basename>` (risk from risk-policy) whenever the basename implied by `source_url` is absent from `mirrors.csv`. This check is **independent of hashdrift** — do **not** require a hash mismatch, and do **not** suppress mirrormiss when hashes already agree. Empty basename does not emit.

5. Provide collision: when **N >= 2** deps in a lane claim the same provide name,
   emit **exactly one** hold string on **every** colliding coordinate:
   `provcollide:<provide>:<c1>|<c2>|…|<cN>` with coordinates sorted ascending.
6. XOR: xor.csv rows are `(lane, group, provide)`. When ≥2 **provide** values from the same `group` appear among lane dep provides, map each provide to **all** dep coordinates that supply it; emit `xor:<group>:<p1>|<p2>` on **every** supplying coordinate. Gate example: `xor:json-codec:json|jsonalt`.
7. Missing pin: dep has no pin row: `missingpin:<coord>`
8. Ban: coordinate in bans -> `ban:<coord>`
9. Version cap: when dep version is strictly greater than max by numeric x.y.z:
   `cap:<coord>:<version>:<max>`

## Totals counters (exact)

`totals` MUST contain **exactly** these thirteen integer keys (no extras):
`release`, `hold`, `remotes`, `hashdrifts`, `versiondrifts`, `mirrormisses`,
`provcollides`, `xors`, `missingpins`, `bans`, `caps`, `cascades`, `risk_score_total`.

- `totals.hold` (and manifest `hold_count`) = count of artifacts with `status` equal to `hold`
  (artifact count, **not** hold-string count).
- `totals.release` = count of artifacts with `status` equal to `release`.
- `risk_score_total` = sum of every artifact's `risk_score`.
- Each prefix counter (`remotes`, `hashdrifts`, `versiondrifts`, `mirrormisses`,
  `provcollides`, `xors`, `missingpins`, `bans`, `caps`, `cascades`) increments
  **once per matching hold string on each artifact** after that artifact's
  hold-string max-risk dedupe. Example: if `dep:jsonA` and `dep:jsonB` each carry
  the same `xor:…` string, `totals.xors` is **2**, not 1. Do **not** use
  once-per-group / once-per-collision / global-unique-string counting.

Lane `lab` with `retention_hops=0` must surface poison hashdrift+versiondrift locally with **no** cascade holds.


## CSV schemas

deps.csv: lane,coordinate,provide,version,source_url,source_hash,patch_url
edges.csv: lane,parent,child,edge_kind
artifacts.csv: lane,coordinate
pins.csv: wrap,version,sha256  (wrap column is the dep basename, keyed as dep:<wrap>)
xor.csv: lane,group,provide
bans.csv: coordinate
forbidden-hosts.csv: host
version-caps.csv: coordinate,max_version
mirrors.csv: basename
risk-policy.csv: kind,risk
cascade-policy.csv: lane,prefix,decay,max_hops
cascade-route-blocks.csv: lane,prefix,block_match
