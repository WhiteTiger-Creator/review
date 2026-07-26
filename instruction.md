Offline EMS ambulance-demand forecasting under `/app/environment` is a machine-learning evaluation task: an online learner scores zone-feature embeddings, held-out arms measure hinge regret against a freeze-epoch checkpoint reconstructed from the weight journal, spectral eigengap packing assigns partition provenance for demand zones, and metamorphic arms (cluster, feature, stream, fuzz) stress adversarial generalization of the scored predictions. Success is a reproducible demand-invariant evaluation artifact at `/app/output/invariant.yaml` whose freeze-epoch inference observations match the offline ML evaluation rules below.

Training-window tip checkpoints can look locally accurate while held-out freeze-epoch inference, spectral zone packing, hinge-regret units, metamorphic noninterference digests, or replay-stable evaluation YAML still violate the contract. Align the model-evaluation libraries under `/app/environment` (zone-feature packing for inference rows, freeze-epoch online-learner checkpoint reconstruction, hinge-regret scoring, metamorphic digest binding, and evaluation YAML emission) with the rules in this instruction, not only a wrapper or a static YAML write. Zone packs use float64 feature vectors. Use the pinned SPL2 evaluation split at `/app/environment/data/pinned_split.lock` and the held-out lane schedule in `/app/environment/data/xtra_lanes.toml`. Held-out and fuzz lanes for the active arm must show zero derived violations. The graded held-out arm is `hold_meta` (seed `41246`, freeze epoch `2`); `hold_fuzz` uses seed `61474` with freeze epoch `2`. Stay offline.

The evaluation entrypoint under `/app/environment` must accept `-root` (default `/app/environment`), `-out` (default `/app/output/invariant.yaml`), and `-arm` (default `1`, first held-out arm). Fresh evaluation of repaired inference-library behavior must rewrite `/app/output/invariant.yaml`; hand-written YAML that skips the model-scoring pipeline is invalid. Consecutive identical evaluations must leave byte-identical artifact bytes (truncate then write). Schema is `demand-invariant-v1`. Each row reports `arm`, `part_tag`, `regret_milli`, `meta_digest`, `cite`, and `cites`, with `part_tag` equal to `cite[-4:]`.

YAML shape:

```yaml
schema: demand-invariant-v1
seed: <uint32 from pinned_split.lock for the active arm>
rows:
  - arm: "<arm name>"
    part_tag: "<last four chars of primary cite>"
    regret_milli: <non-negative int>
    meta_digest: "<16 lowercase hex chars>"
    cite: "<primary opaque row tag>"
    cites:
      - "<opaque row tag>"
```

Zone packs under `/app/environment/fixtures/zones/*.bin` (little-endian): magic `ZNF1`, `u16` zone count, `u16` feature count, `u32` pack stamp, then records of `u16` zone id, `i16` label in `{+1,-1}`, then `feature_count` float64 feats. The evaluation pack stamp is the maximum stamp across packs.

Base checkpoint `/app/environment/weights/w_base.bin`: magic `WB01`, `u16` dim, `dim` float64 weights, float64 bias. Weight journal `/app/environment/weights/w_journal.bin`: magic `WJ01`, `u16` dim, `u32` record count, then records of `u32` epoch, `dim` float64 delta_w, float64 delta_b (additive). Tip snapshot `/app/environment/weights/frozen_w.bin` (magic `FW01`) is the journal tip after every record and must not be used alone for held-out scoring. For active arm freeze epoch `F` from the SPL2 lock: start from `w_base.bin`, apply journal records with `epoch <= F` in ascending epoch order; that reconstructed checkpoint is the only legal scoring weights for the arm.

Pinned split `/app/environment/data/pinned_split.lock`: magic `SPL2`, `u16` arm count, each arm 16-byte NUL-padded name, `u8` kind (`0` train, `1` held-out), `u32` seed, `u32` freeze_epoch.

Partition cache `/app/environment/data/part_cache.bin`: magic `PC01`, `u32` stamp, `u32` freeze_epoch, `u16` cite count, then 12-byte NUL-padded cite tags. Valid only when stamp equals the current maximum zone-pack stamp and freeze_epoch equals the active arm freeze epoch; otherwise rematerialize via the eigengap cut and rewrite the cache.

Run tip `/app/environment/data/run_tip.bin` may hold crashed residue. Each fresh evaluation must clear tip state before committing. Stages commit pack, freeze-weight, and regret fingerprints for the active arm index; YAML emission is valid only when all three tips agree on that arm.

Eigengap packing: load every zone; mean_i is the arithmetic mean of zone i features; sort by ascending mean_i then zone id; cut after the left zone of the maximum successive mean gap (partitions `0` then `1`); emit rows sorted by `(partition_id, zone_id)`; cite tag `z` + four zero-padded hex zone id + `p` + two zero-padded hex partition id (example `z0001p00`).

Regret on packed rows with freeze-epoch weights w and bias b: score_i = w · x_i + b; hinge_i(y, s) = max(0, 1 - y * s) for y in `{+1,-1}`; L_learner = sum hinge_i(y_i, score_i); L_best = min(sum hinge_i(y_i, +1), sum hinge_i(y_i, -1)); regret = (L_learner - L_best) / max(1, n); regret_milli = round(1000 * regret), clamped >= 0.

Metamorphic digests for lanes in `/app/environment/data/xtra_lanes.toml` (`kind` in `{cluster, feature, stream, fuzz}`): payload `{salt}{kind}|{seed}|{arm}|{sorted_zone_keys}|{regret_milli}` where sorted_zone_keys are the 4-hex zone id fields from cites (`zHHHH`), sorted ascending and comma-joined, and salt is `C:` / `F:` / `S:` / `Z:<fuzz_rounds>:` / `X:`. meta_digest is the first 8 bytes of sha256(payload) as 16 lowercase hex chars. Primary YAML meta_digest is the `hold_cluster` lane digest when present.

Default `-arm` is the first held-out arm (`hold_meta`). Evaluating twice against the same root and output path must leave byte-identical YAML, including under a warm rewritten partition cache.
