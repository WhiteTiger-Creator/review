Certify TrustLoom's TL-ALS-CONF-1 implicit-feedback collaborative filter on the spare-parts pick co-occurrence logs under `/app/data`. The trainer under `/opt/trustloom` still runs an outdated ALS path, so fitted factors, query scores, holdout ranking metrics, remassed stride folds, and fit diagnostics miss the shipping card on confidence locality, ridge jitter, update order, conditional fade, packing, polarity alignment, and degree-damped scoring.

Authoritative docs (read in order; later wins on conflict):
1. `/app/model-card/trustloom-spec.txt`
2. every file under `/app/model-card/errata/` sorted by filename

`/app/docs/als-handbook.md` section 3.1 Final applies only when it does not conflict with those. Ignore handbook drafts, `/app/notes/`, and any sklearn / Vowpal notes.

Implement the full TL-ALS-CONF-1 training and evaluation recipe from that chain in `/opt/trustloom`. Grading rebuilds `/opt/trustloom` from source before scoring.

Required run (exit 0):

`/opt/trustloom/bin/trustloom --interactions /app/data/interactions.csv --queries /app/data/queries.csv --holdout /app/data/holdout.csv --out /var/lib/trustloom`

Required artifacts (all produced by the single command above):
- `/var/lib/trustloom/model.json` — packed user/item factors
- `/var/lib/trustloom/scores.json` — query scores
- `/var/lib/trustloom/metrics.json` — holdout ranking metrics
- `/var/lib/trustloom/diagnostics.json` — fit diagnostics
- `/var/lib/trustloom/folds.json` — remassed stride-fold MAP checks

All five must satisfy the full normative chain for the bundled inputs and for other contract-conforming inputs of the same shape.
