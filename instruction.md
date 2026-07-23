After a layout bump, continued offline runs still show falling loss and ordinary rank
histograms, but held-out score collapses versus a baseline run that uses the same seed
and the same transition corpus. Rebuilding the store from raw transitions restores the
score; loading the already-migrated store does not. Resume after a torn journal tail,
assess-after-migrate, and a second migrate/fence also drift on shadow watermarks, draw
ceilings after generation bumps, and payload digests.

Fix sources under `/app/environment`, rebuild with `make -C /app/environment install`,
and regenerate observations through the normal pipeline. Drive scenarios with
`bash /app/environment/scripts/run_matrix.sh <case>` and `/app/bin/lanectl`
(migrate, train, resume, assess, inspect, replay). Durable state under STATE_DIR uses
`snap.json`, `journal.ndjson`, and `shadow.json`. The verifier regenerates those flows;
static or manual output writes are not enough.

Caps and formulas live in `/app/environment/configs/train.toml` and
`/app/environment/docs/operator_contract.md` (seed 77103, eval band 0.05, duplicate-rank
ceiling at least 0.85 with upper-bin skew at least 0.12, v1 to v2 migrate with payload
preservation, v2 reload idempotence, torn-journal recover with replay_delta 0, generation
bump ceilings stable within 5% across the last three post-bump draws, assess within band
of final train scoring). Final draw `era` must equal inspect `live_gen`. Replay must leave
the last training step ordinal unchanged. Emit `/app/output/training_observations.json`
with seed, runs, scenario, steps, draws, scoring, ordinal, loss, rank_histogram, span,
ceiling, era, heldout_score, baseline_score, payload_digest, shadow_seal, fence_gen,
journal_epoch, and replay_delta. Emit `/app/output/halt_audit.json` with scenario,
halt_step, gen_mark, live_gen, meta_digest, bindstamp, fence_gen, journal_epoch, and
shadow_seal. Emit `/app/output/replay_audit.json` with scenario, journal_entries,
chain_gap, fence_gen, shadow_seal, and replay_stamp. Loss stability alone is not success:
held-out scoring must stay in the baseline band after migrate-load, draw ceilings must
stay commensurate with rebuild-from-corpus, and after halt/continue gen_mark, final draw
era, and fence_gen must agree with live state. Inspect bindstamp must stay stable across
two inspects and include the shadow seal. Replay must rebuild its audit without advancing
training and keep chain_gap at 0 when healthy.

Do not wipe the store and retrain, tweak one anneal knob, or rewrite only the emitter.
