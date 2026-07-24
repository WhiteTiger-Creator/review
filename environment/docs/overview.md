# Culvert intake inference pipeline

The Java sources under `src/main/java/com/culvert` implement an offline batch inference scorer for intake ranking model evaluation.

`Flow` loads a JSON case file, builds an affinity view, applies window coupling, selects a partition count from the eigengap spectrum, and writes a YAML summary to `/app/output/culvert_rank.yaml` for training-serving parity review under frozen weights.

Supporting modules also live under `partition/`, `stream/`, and `merge/` at the environment root.

Entry script is `scripts/replay.sh`. Behavioral contracts for windowing, partition selection, ranking, digests, and metamorphic stability are in `replay_contract.md`.
