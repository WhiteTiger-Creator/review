# Offline ML evaluation contract: ambulance-demand online-learner regret

This document is the public source of inference formulas, binary layouts, evaluation-split policy, freeze-epoch checkpoint reconstruction, partition-cache validity, tip-agreement for scored stages, and metamorphic survival rules for the offline machine-learning evaluation. The inference stack under `/app/environment` must satisfy every rule below when invoked through the documented evaluation entrypoint.

## Artifact

Path: `/app/output/invariant.yaml`

The file must be produced by the published offline inference evaluation pipeline. Static hand-written files that skip zone packing, freeze-epoch weight reconstruction, hinge-regret folding, tip agreement, or metamorphic digest binding are invalid even when schema-shaped. Consecutive evaluations with the same inputs must be byte-identical (truncate then write; no append residue).

## YAML schema (`demand-invariant-v1`)

```yaml
schema: demand-invariant-v1
seed: <uint32 from pinned_split.lock for the active arm>
rows:
  - arm: "<arm name>"
    part_tag: "<last four chars of primary cite, encoding partition>"
    regret_milli: <non-negative int>
    meta_digest: "<16 lowercase hex chars>"
    cite: "<primary opaque row tag>"
    cites:
      - "<opaque row tag>"
```

No boolean verdict fields are permitted. Field values are observations derived from the rules below.

## Zone-feature packs

Files under `/app/environment/fixtures/zones/*.bin` use little-endian layout:

- magic `ZNF1`
- `u16` zone count, `u16` feature count, `u32` pack stamp
- repeated records: `u16` zone id, `i16` label in `{+1,-1}`, then `feature_count` float64 `feats`

The evaluation pack stamp is the maximum stamp across all zone packs.

## Base checkpoint and weight journal

Held-out scoring must **not** use the tip snapshot at `weights/frozen_w.bin` alone.

`weights/w_base.bin`:

- magic `WB01`
- `u16` dim, then `dim` float64 weights, then float64 bias

`weights/w_journal.bin`:

- magic `WJ01`
- `u16` dim, `u32` record count
- each record: `u32` epoch, `dim` float64 `delta_w`, float64 `delta_b` (additive updates)

`weights/frozen_w.bin` (magic `FW01`, same body shape as base) is the **journal tip** after applying every record. It is a diagnostic tip snapshot only.

### Freeze-epoch reconstruction

For the active arm with freeze epoch `F` from `pinned_split.lock`:

1. Start from `w_base.bin`.
2. Apply every journal record with `epoch <= F`, in ascending epoch order.
3. The resulting weights are the only legal scoring checkpoint for that arm.

## Pinned split (`SPL2`)

`/app/environment/data/pinned_split.lock`:

- magic `SPL2`
- `u16` arm count
- each arm: 16-byte name (NUL padded), `u8` kind (`0` train, `1` held-out), `u32` seed, `u32` freeze_epoch

Training versus held-out arms follow this lock. Held-out arms listed in `xtra_lanes.toml` must report zero derived violations.

## Partition cache

`/app/environment/data/part_cache.bin`:

- magic `PC01`
- `u32` stamp, `u32` freeze_epoch, `u16` cite count
- repeated 12-byte NUL-padded cite tags

The cache is **valid** only when `stamp` equals the current maximum zone-pack stamp **and** `freeze_epoch` equals the active arm freeze epoch. Invalid or missing caches must be rematerialized by the eigengap cut rule and rewritten. Warm reuse of a mismatched cache is non-compliant.

## Run tip journal

`/app/environment/data/run_tip.bin` may contain residue from a prior crashed evaluation. Each fresh evaluation must clear tip state before committing stages.

Stages commit fingerprints for the active arm index in order:

1. Pack tip over ordered cite tags
2. Freeze-weight tip over reconstructed weights and freeze epoch
3. Regret tip over arm name, seed, regret_milli, and cites

YAML emission is valid only when all three tips agree on the same arm index. Emission without tip agreement is non-compliant.

## Eigengap cut rule (feature packing)

1. Load every zone record from the zone packs.
2. Let `mean_i` be the arithmetic mean of zone `i` features.
3. Sort zones by ascending `mean_i`, breaking ties by ascending zone id.
4. For each successive pair in that order, compute gap `mean_{j+1} - mean_j`.
5. Place a single cut after the left zone of the maximum gap (two partitions, ids `0` then `1`). Equivalently: the first index of partition `1` is one past the left zone of the max gap.
6. Emit rows sorted by ascending `(partition_id, zone_id)`.
7. Opaque cite tag format: `z` + four zero-padded hex zone id + `p` + two zero-padded hex partition id (example shape `z0001p00`). The YAML `part_tag` field equals `cite[-4:]`.

Absolute file order or zone-id order without the cut is not compliant.

## Regret metric

For an arm with packed rows and **freeze-epoch** weights `w`, bias `b`:

- score_i = w · x_i + b
- hinge_i(y, s) = max(0, 1 - y * s) with label y in `{+1,-1}`
- L_learner = sum_i hinge_i(y_i, score_i)
- L_best = min( sum_i hinge_i(y_i, +1), sum_i hinge_i(y_i, -1) )
- regret = (L_learner - L_best) / max(1, n)
- `regret_milli` = round(1000 * regret), clamped to be >= 0

Scoring against the tip snapshot (`frozen_w.bin`) is non-compliant for held-out arms.

## Metamorphic noninterference digests

Held-out lanes in `/app/environment/data/xtra_lanes.toml` have `kind` in `{cluster, feature, stream, fuzz}`.

For lane L and regret unit U, build payload:

`kind_salt + kind + "|" + seed + "|" + arm + "|" + sorted_zone_keys + "|" + regret_milli`

where `sorted_zone_keys` are the 4-hex zone id fields parsed from each cite tag (the `zHHHH` portion), sorted ascending and joined by commas, and `kind_salt` is `C:` / `F:` / `S:` / `Z:<fuzz_rounds>:` / `X:` for other kinds.

Concrete payload string before hashing:

`{salt}{kind}|{seed}|{arm}|{sorted_zone_keys}|{regret_milli}`

`meta_digest` is the first 8 bytes of sha256(payload) encoded as 16 lowercase hex characters.

The primary YAML `meta_digest` is the digest for the `hold_cluster` lane when present.

Property-based fuzz lanes (`kind = fuzz`) must also yield zero derived violations under this predicate across `fuzz_rounds`.

## Split and quality policy

- Default evaluation arm for the published entrypoint is the first held-out arm in `pinned_split.lock` (index 1: `hold_meta`) unless `-arm` overrides.
- Training arms may be used for diagnostics but do not satisfy held-out survival.
- Quality gate: every lane in `xtra_lanes.toml` whose `arm` matches the active arm name must have a digest that recomputes identically from the public payload rule.

## Rerun stability

Evaluating twice against the same root and output path must leave `/app/output/invariant.yaml` byte-identical. The second evaluation must still rematerialize correctly under a warm, previously rewritten partition cache.

## Offline

No network egress. All inputs are local under `/app/environment`.
Binary fields are little-endian struct layouts.

## Held-out seeds and freeze epochs

The `hold_fuzz` arm seed must be `61474` with freeze epoch `2`.
The `hold_meta` arm seed must be `41246` with freeze epoch `2`.
