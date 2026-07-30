# Curtailment desk rule simulator

Headless simulator for IEC 61850 SCL plant curtailment rule enforcement.
Primary activity is engine rule enforcement, save-state journaling, and
deterministic replay scoring.

Rule annex lives in `annex/slice_137.txt`.
Plant fixtures live in `fixtures/`.
Closed, arm-omit, and permutation scenario packs live in `corpora/`.
Engine notes live in `docs/`.
Playthrough binary is `/app/build/regret_solver` via `pvsim`.

Primary products are dossier and transcript JSON under `/app/runtime/`.
Each emit also writes durable save shards under `/app/runtime/journal/`.
