# Operator contract

## Commands

```bash
bash /app/environment/scripts/run_matrix.sh <case>
/app/bin/lanectl migrate --scenario ID --config /app/environment/configs/train.toml \
  --pack /app/environment/data/pack_rows.json --state STATE_DIR \
  --out /app/output/training_observations.json
/app/bin/lanectl train --scenario ID --mode MODE --config /app/environment/configs/train.toml \
  --pack /app/environment/data/pack_rows.json --state STATE_DIR \
  --out /app/output/training_observations.json
/app/bin/lanectl resume --state STATE_DIR --config /app/environment/configs/train.toml \
  --pack /app/environment/data/pack_rows.json --out /app/output/training_observations.json
/app/bin/lanectl assess --state STATE_DIR --out /app/output/training_observations.json
/app/bin/lanectl inspect --state STATE_DIR --out /app/output/halt_audit.json
/app/bin/lanectl replay --scenario ID --state STATE_DIR --out /app/output/replay_audit.json
```

`run_matrix.sh` reads case ids from `/app/environment/data/matrix_cases.json`. Modes include
`baseline`, `migrate_load`, `rebuild`, `idempotent`, `twin_mass`, `hybrid_halt`,
`torn_resume`, `gen_bump`, `assess_migrate`, `double_fence`, and `halt_twin`.
Segmented halt cases stop in one invocation and resume from the same `STATE_DIR`.

## Durable state under STATE_DIR

- `snap.json` — heap, meta, live_gen, step_ordinal, baseline_score, scenario
- `journal.ndjson` — append-only frames (`migrate`, `train`, `halt`, `fence`); a torn
  trailing line must be ignored on resume/replay
- `shadow.json` — schedule watermark: `alpha`, `schema`, `payload_seal` (64 hex),
  `fence_gen`, `journal_epoch`

Layout migration is staged then sealed: staged slot weights become live sampling weights
only after a durable fence. Live draw ceilings use live-era `mass` over the full window.
After migrate+fence, live mass equals `raw_p ** alpha_v2` and transition payload bytes match
a same-seed rebuild-from-corpus store (`payload_digest` equal).

## Training observations

`/app/output/training_observations.json` is rewritten on every finished driver run.

Top-level fields:

- `seed` (integer): fixed training seed, `77103`
- `runs` (array): one entry per scenario executed in the run

Each run:

- `scenario` (string): case id
- `steps` (array): ordered training steps
- `draws` (array): draw-scale observations
- `scoring` (object): held-out comparison fields

Each step:

- `ordinal` (integer): zero-based step index
- `loss` (number): scalar loss for the step
- `rank_histogram` (array of integers): binned mass histogram for the live heap

Each draw:

- `ordinal` (integer): step index for the draw
- `span` (number): summed live-era mass used for the draw window
- `ceiling` (number): max live-era mass used to scale importance weights
- `era` (integer): live generation marker applied to the draw

Each scoring object:

- `heldout_score` (number): held-out eval after the run
- `baseline_score` (number): score from a rebuild-from-corpus reference at the same seed
- `payload_digest` (string): 64-character lowercase hex SHA-256 over length-prefixed
  transition payload blobs
- `shadow_seal` (string): 64-character hex watermark from `shadow.json`
- `fence_gen` (integer): fence generation from the shadow ledger
- `journal_epoch` (integer): journal epoch from the shadow ledger
- `replay_delta` (number): `0.0` when resume/replay is idempotent with durable bytes

Held-out eval must stay within relative band `eval_band_rel = 0.05` of `baseline_score`:

```
abs(heldout_score - baseline_score) / max(abs(baseline_score), 1e-12) <= 0.05
```

After migrate-load, draw `ceiling` values must stay within 5% of a same-seed
rebuild-from-corpus run. Assess after migrate must keep held-out within the same band of
the last train scoring held-out.

Draw ceilings under adversarial duplicate ranks must include the high-priority upper-half
mass (`ceiling >= twin_ceiling_min = 0.85` after the active schedule) and keep a visible
upper-bin load in the final `rank_histogram` (upper-vs-lower skew at least
`twin_skew_max = 0.12`).

Generation bumps occur when `ordinal % 5 == 0` (for ordinal > 0). Subsequent draw ceilings
must reflect post-bump live-era masses, not a stale pre-bump window.

A second v2 migrate/fence must leave `payload_digest`, `shadow_seal`, and `replay_delta`
stable (`replay_delta == 0.0`). Transition payload bytes must survive torn-journal recovery
and fencing; wiping the durable store and retraining from scratch is out of contract.

## Halt audit

`/app/output/halt_audit.json` is rewritten by `lanectl inspect` from durable state without
advancing training.

Fields:

- `scenario` (string)
- `halt_step` (integer): step ordinal sealed in durable meta
- `gen_mark` (integer): durable generation marker
- `live_gen` (integer): live trainer generation at inspect time
- `meta_digest` (string): durable meta digest hex
- `bindstamp` (string): 64-character lowercase hex SHA-256 over scenario, halt step,
  gen mark, meta digest, and shadow seal
- `fence_gen` (integer)
- `journal_epoch` (integer)
- `shadow_seal` (string): 64-character hex

After halt/continue, `gen_mark` must equal `live_gen`, the final draw `era` must equal
`live_gen`, and `fence_gen` on the audit must match the shadow ledger. Inspect bindstamp
must be stable across two inspect calls and include the shadow seal in its material.

## Replay audit

`/app/output/replay_audit.json` is rewritten by `lanectl replay` from durable bytes without
advancing training.

Fields:

- `scenario` (string)
- `journal_entries` (integer): count of valid journal frames
- `chain_gap` (integer): `0` when the journal/shadow chain is healthy
- `fence_gen` (integer)
- `shadow_seal` (string): 64-character hex
- `replay_stamp` (string): 64-character hex over scenario, entry count, fence gen, and seal

Torn last journal lines must recover from `snap.json` with `replay_delta == 0.0` after
successful recover+continue and `chain_gap == 0` on replay.

## Public caps

From `/app/environment/configs/train.toml`:

- seed = 77103
- alpha_v1 = 0.6
- alpha_v2 = 0.4
- beta = 0.5
- schema_v2 = 2
- train_steps = 12
- hist_bins = 8
- eval_band_rel = 0.05
- twin_skew_max = 0.12
- twin_ceiling_min = 0.85

Exact reruns at the same seed and case must produce byte-stable observation files.

## Anti-decoy rules

Wiping the store and retraining, tweaking a single anneal knob, rewriting only the
observation emitter, or writing observation JSON directly without running the pipeline
are invalid.
