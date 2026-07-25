# Evaluation ledger and quantized model promotion

Offline ETA residual evaluation is bound to a model-registry generation. Inference knobs (feature scale mode and graph/lane mix) are promoted through a staged commit workflow. Evaluation writes a ledger entry that records the generation and epoch token used for that run document.

## CLI

All commands take `--root /app/environment` unless noted.

```
/app/environment/bin/etaengine status --root /app/environment
/app/environment/bin/etaengine stage --root /app/environment --scale-mode peak --graph-weight 0.005 --lane-weight 0.995
/app/environment/bin/etaengine finalize --root /app/environment
/app/environment/bin/etaengine commit --root /app/environment
/app/environment/bin/etaengine rollback --root /app/environment
/app/environment/bin/etaengine evaluate --root /app/environment --fixture <name> --family <family> --seed <n> --out /app/output/run_doc.json [--key <ledger-key>]
/app/environment/bin/etaengine replay --root /app/environment --key <ledger-key> --out /app/output/run_doc.json
```

Fixtures: `batch_00`, `batch_01`, `batch_02` under `/app/environment/testsupport/fixtures/`. Families: `base`, `unit`, `order`, `pad` (profiles `base`, `alpha`, `beta`, `gamma`).

## Authority and generations

- `state/registry.json` owns `active_generation`, active `settings` (including `scale_mode`, `graph_weight`, `lane_weight`), `epoch_token`, `lineage`, and `settings_by_gen`. Field `scale_mode` means the feature-scale policy applied during prep (`declared` uses manifest scale; `peak` uses batch peak-norm).
- `state/staged.json` holds a candidate promotion. Staging always starts with `incomplete=true`.
- `finalize` clears incompleteness on the staged candidate.
- `commit` may activate a staged candidate only when it is complete (`incomplete=false`). After a successful commit, staged state must be removed and `settings_by_gen` must record the new generation settings.
- `evaluate` must use **active** registry settings and label outputs with **active** generation and epoch token. Staged candidates must not affect evaluate until committed.
- `rollback` restores the previous generation: `active_generation` becomes `int(active_generation) - 1`, `settings` come from `settings_by_gen` for that prior generation, and `epoch_token` is refreshed. Staged state is discarded.

## Ledger and replay

- Each evaluate appends one line to `state/ledger.jsonl` with key, generation, fixture, family, seed, out_path, epoch_token.
- Default key is `fixture:family:seed` (example: `batch_01:pad:887`).
- `replay` must re-run inference under the **current active** settings when the ledger entry generation or epoch token does not match the active registry. Copying a prior output file is allowed only when generation and epoch token still match.

## Output document

Path: `/app/output/run_doc.json` (or path passed to `--out`). Alternate evaluate destinations such as `/app/output/pre_replay.json` are valid regenerated output paths when a ledger key records that location for later replay comparison.

- `version` = 1
- `runs[]` with `instance_id`, `family`, `seed`, `score`, `observed`, `delta`, `profile`, `generation`
- `summary.instance_count`, `summary.families` (sorted), `summary.generation`, `summary.model_id`
- Identity: `abs(float(delta) - (float(score) - float(observed)))` must be within `1e-5`.
- Every run `generation` equals `summary.generation` and equals registry `active_generation` at evaluate time

## Metamorphic contracts (active generation settings)

T1: for matched base/perturbed rows, `abs(delta_base - delta_perturbed) <= max(1e-4, 0.008 * max(abs(delta_base), abs(delta_perturbed), 1.0))`.

D1: every `|score| > 0.08` and `max(|score|) > 0.12`.

M1: every `|score| <= 4 * declared_scale` from `assets/manifest.json`.

Score ordering: when `observed` is non-decreasing by `instance_id`, adjacent rows satisfy `float(score) - float(score) <= 0.05` (earlier minus later; symmetric for decreases).

Production settings that satisfy T1/D1 under metamorphic families use peak scale mode with lane-primary mix (`graph_weight` near 0.005, `lane_weight` near 0.995). Manifest `declared_scale` remains the M1 envelope only.
