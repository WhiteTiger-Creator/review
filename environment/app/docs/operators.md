# Operators notes

Node 0352 runs numerical barrier margin analysis through the local Java jar built from `/app/environment`. Build with `make -C /app/environment`. The wrapper `/app/exec/diff_run` rebuilds when sources change.

Pack fixtures live under `/app/environment/app/data/`. Reference table bases are in `ref_q7_pack.json`. Use `app/tools/inspect.sh` for a quick cluster count on a pack file.

Schema for emitted JSON is `/app/environment/schemas/q8_report.schema.json`. Full formulas and O1 rules are in `k4_surface.md`.
