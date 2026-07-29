# K7 held-out ML evaluation harness

Offline **machine-learning** held-out **inference evaluation**: bundled instrument captures, `wt_pair` eval shards, and reference scoring via `/opt/k7probe/dy` produce witness-reduction metrics in `/app/output/k7_witness_report.json`.

Normative evaluation contracts: `/app/environment/docs/EVAL.md`, `/app/environment/docs/MODEL.contract`, `/app/environment/docs/FORMAT.contract`, and `/app/environment/docs/COLS.md`. Informal `EVAL_SHORTCUTS.md` is a non-authoritative decoy. Operator flow: `/app/environment/tools/check-k7.sh` after recompiling the worker from this directory (Makefile targets).

Runtime base is the digest-pinned canonical `golang:1.24-bookworm` image.
