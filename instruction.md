Train an importance-weighted marked Hawkes model in R through /app/run.sh.
Learn cluster-held-out event scores for every policy, then search the prescribed
randomized policy portfolios. Portfolio branching includes pairwise and
three-way nonlinear switching excitation, so values, support, dispersion,
stability, and feasibility must be
recomputed after every one-cluster and two-cluster deletion. Select the robust
full portfolio and independently certify the nested deletion surfaces.

Read the bundle from the first argument, defaulting to /app/data, and atomically
replace the CSV at the second argument, defaulting to
/app/outputs/results.csv. The complete validation, numerical, portfolio,
selection, certificate, and audit contract is in
/app/docs/OUTPUT-CONTRACT.md.

Derive all results from the supplied bundle. Hidden bundles vary labels,
geometry, time scale, switching strength, support boundaries, and influential
cluster pairs. Results must be deterministic and representation-invariant.
Reject malformed bundles without creating or replacing the destination.
Internet access is unavailable; only base R is guaranteed.
