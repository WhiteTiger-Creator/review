# K4 surface contract

Node 0352 CCS obligation O1 requires zero feasibility violations on the closed fixture algebra. A violation occurs when any assembled barrier margin is negative or when witness row margins disagree with the barrier vector for the same cluster index.

## 1. Lattice labels

Labels are `L0` through `L3` with ranks 0, 1, 2, 3 respectively. Pack JSON under `/app/environment/app/data/` supplies per-cluster label maps. Held-out packs may permute cluster order via `permute_order`.

## 2. Annex cue material

`SliceQ7` extracts cue bytes per cluster from pack `cue_clusters`. Each cluster record includes `cluster_id`, hex `cue_bytes`, and `boundary` flag. Cue slice bytes place the boundary sentinel at index 4 when `boundary` is true.

### Cue hash

For cue bytes `b[0..n-1]`:

```
H(b) = (sum of unsigned byte values) mod 1009
```

### Arm salt

```
salt(arm_id) = (arm_id * 131) mod 997
```

### Narrowing at boundary

When `cueSlice[4] & 0x01` is nonzero, the narrowed label rank is the minimum rank between the pack label for the cluster and the **already narrowed** neighbor cluster label listed in `neighbor_id` on the cluster record. Otherwise use the pack label unchanged.

For held-out permutations (`permute_order` present), cluster processing follows that order when pairing neighbors; when `applyPermute` is false, use pack cluster declaration order.

## 3. Barrier margin vector

Reference table `/app/environment/app/data/ref_q7_pack.json` fields:

| field | type | role |
|-------|------|------|
| `row_keys` | string array | cluster ids aligned to margin indices |
| `table_bases` | int array | subtractive base per row |
| `cue_hashes` | int array | precomputed `H(cue_bytes)` per `row_keys` entry |

Pack JSON files expose `label_map` (cluster id to `L0`..`L3`) and `cue_clusters` with hex `cue_bytes`.

Given narrowed label rank `r`, cue hash `h` from `cue_hashes[i]`, arm salt `s`, and subtractive base `base[i]`:

```
margin_i = h + s + r - base[i]
```

Subtractive bases default to reference `table_bases`. When a pack defines `margin_bases`, use those values aligned to `row_keys` instead (see `binding_profiles.md`).

Row keys in the table align with cluster ids. All margins must be non-negative for O1 feasibility.

## 4. Stress draw policy

`/app/environment/app/data/k9_k7_pack.json` lists weighted draws per wave (`w0`, `w1`). Only draws whose `arm_id` matches the active pack arm contribute weight and margin boosts. For each matching draw targeting `cluster_id` with weight `w`, add `floor(w * scale)` where `scale` is the wave multiplier from `binding_profiles.md`. Termination requires the sum of applied draw weights (matching arm only) to reach at least `termination_weight` (0.85) on stress runs.

## 5. Witness rows and replay deltas

Each witness row contains:

| field | type | rule |
|-------|------|------|
| `arm_id` | int | active arm |
| `cluster_id` | string | cluster key |
| `margin` | int | must equal `barrier_margins[index(cluster_id)]` |
| `ref` | string | `w-` + first 12 hex chars of **SHA-256** over `arm_id|cluster_id|margin` (via `sha256sum` or Java SHA-256) |

Replay deltas chain across trace steps for the same `arm_id`:

```
delta_step = margin_step - margin_previous
```

For the first step on an arm, `delta_step = 0`. Parallel fork branches inside one dossier must share identical deltas for the same `(arm_id, cluster_id)` pair.

## 6. Idempotent merge

Sort witness `ref` strings ascending. Build the merge preimage by joining every sorted `ref` with `|`, then append `|`, then `case_id`, then `|`, then `run_mode` (ASCII pipe `0x7c` between each segment):

```
body = ref0|ref1|...|refN-1|{case_id}|{run_mode}
merge_token = first 16 hex chars of SHA-256(body)
```

Example (direct mode, case 352): if sorted refs are `w-abc` and `w-def`, then `body = "w-abc|w-def|352|direct"`.

Rerunning `diff_run` with identical inputs must reproduce the same `merge_token` and must not duplicate `ref` values.

## 7. CLI

`/app/exec/diff_run` options:

| flag | meaning |
|------|---------|
| `--case N` | case id (352 for node 0352) |
| `--mode direct` | training pack `pack_t352.json` |
| `--mode held` | held pack `pack_h0352.json`; add `--permute` to apply `permute_order` |
| `--mode stress` | stress draws from `k9_k7_pack.json`; `--wave w0` or `--wave w1` |

Example invocations:

```
/app/exec/diff_run --case 352 --mode direct
/app/exec/diff_run --case 352 --mode held --permute
/app/exec/diff_run --case 352 --mode stress --wave w0
/app/exec/diff_run --case 352 --mode stress --wave w1
```

Output path is always `/app/output/diff_replay_dossier.json`.

Replay trace framing order for held permute runs is defined in `binding_profiles.md`.
