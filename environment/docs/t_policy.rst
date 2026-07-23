# T Policy

Thermal DTMC workflow for pile-layer certification: microbial heat-balance residuals under floating-point tolerances, schedule ranking, independent seal replay, and closed-algebra YAML seals.

## Obligation

Closed fixture algebra: for every bundled thermal instance (training arm `train_a`, stress arm `host_b`, and every aeration-order id in `/app/environment/data/perm_tbl.toml` in file order), probabilistic model-checking violations must be zero under the residual tolerance class below.

## Residual tolerance class

Interlayer mass residual for each adjacent pair edge `e` between layers `i` and `i+1` is the sum of assignment uses on that edge minus the effective capacity for that edge.

Nominal capacity comes from `[edges]` in `/app/environment/data/pack_c/nrg.toml`. Signed reclaim adjustments come from `[reclaim]` in the same file (missing keys mean reclaim `0.0`). Effective capacity is:

`eff(e) = capacity(e) - reclaim(e)`

A violation is counted when `joint_use(e) > eff(e) + tol` with `tol = 1.0e-9` from the `[eps]` table. The residual stored for digests is `joint_use(e) - eff(e)`. Per-layer checks alone are not sufficient; joint accounting across adjacent layers is required. Raw nominal capacity without reclaim does not define the residual class.

## Ranking multipliers

Schedule ranking multipliers are loaded from `/app/environment/data/pack_c/nrg.toml` as `hint_mul` and `lane_mul` (wrapping u32). Scoring must use those binders, not compiled-in substitutes.

For index `i`, score = `hints[i] * hint_mul + layer_ix[i] * lane_mul` (wrapping u32). Sort indices by descending score, tie-break ascending index. `ranks[i]` is the resulting position.

## Matrix node tags

Thermal constraint rows are sorted by the lexicographic string form of their sorted literal tuples (comma-joined decimal literals, content-addressed order). For each row at 0-based index `i`, sort literals by `(ranks[|lit|-1], lit)`, then mix with:

`acc = 0xC0FF0000 xor i; acc = acc * 16777619 + ranks[|lit|-1] * 37 + (lit as u32)`

Collect tags, sort ascending, and deduplicate.

## Journal stitch

Arms are processed in this fixed order: `train_a`, then `host_b`, then each aeration-order id from `/app/environment/data/perm_tbl.toml` in file order. A running annex journal starts as empty bytes before the first arm. Generation counter starts at `0` and advances by one on each arm attempt.

For each arm, form the arm-local journal fragment:

- UTF-8 `arm_id` bytes
- then the arm generation as `u32` little-endian (`prev.gen` wrapping-add `1`)
- then each matrix node tag as `u32` little-endian (tags sorted ascending and deduplicated)

Let `prev` be the running journal before this arm.

- If the arm has any residual violation (`viol_n != 0`), the stitched journal for this arm is a copy of `prev` (rollback of the partial seal). The running journal stays `prev`. Generation still advances for state bookkeeping, and sealed state keeps the prior arm blob.
- If the arm has zero violations, the stitched journal is `prev` concatenated with the arm-local fragment, and the running journal advances to that concatenation.

## Digest formulas

For each arm row, let `payload` be the concatenation of:

- `arm_id` as UTF-8 bytes
- for each node tag in ascending order: `u32` little-endian
- for each edge key in lexicographic order: `f64` little-endian joint residual after effective-capacity subtraction
- eight bytes: first eight bytes of sha256 over the stitched annex journal for that arm

`digest_hex` is the lowercase hex encoding of sha256(`payload`).

Stage seal bytes for each arm: lowercase hex of sha256 over the concatenation of ASCII `seal/t1:`, the witness raw bytes for that arm, and the first eight bytes of sha256 over the stitched annex journal. The seal hex is always 64 lowercase hex characters (`seal_mark` is `1` only at that length). Early stage gauges under `/app/output/stage` may read green; they do not truncate or replace this seal formula. Independent certificate replay must re-verify from sealed material alone without trusting construction-time caches.

`seal_hex` is lowercase hex of sha256 over the concatenation of every row `digest_hex` (UTF-8) in ascending `arm_id` order, then a single `u32` LE equal to the total violation count across arms.

`closed_n` is `1` when every row has `viol_n == 0`, every row has `seal_mark == 1`, and `seal_hex` matches this formula; otherwise `0`.

`util_max` is the maximum over arms of `joint_use(e) / max(eff(e), 1e-12)` across edges (floating-point). The emitted `util_max` must match that computed value within absolute tolerance `1.0e-9`. Utilization audits catch engines that ignore schedule pressure once probability mass looks locally normalized.

`eps_used` must equal `1.0e-9` from the policy `[eps]` table.

## Bundle schema

`/app/output/invariant_bundle.yaml` object fields:

- `schema_ver` (integer): must be `1`
- `rows` (array of objects), each with:
  - `arm_id` (string)
  - `digest_hex` (string, 64 lowercase hex chars)
  - `viol_n` (integer, non-negative)
  - `eps_used` (number, must equal `1.0e-9`)
  - `seal_mark` (integer `0` or `1`)
  - `stage_mark` (integer `0` or `1`) early gauge only; not authoritative
- `util_max` (number)
- `seal_hex` (string, 64 lowercase hex chars)
- `closed_n` (integer `0` or `1`)

Stage gauges under `/app/output/stage` may turn green early. Only the sealed YAML from `hv7` counts. Hand-written YAML that was never emitted by `hv7` from the live modules does not satisfy the regenerate rule.
