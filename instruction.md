Train and evaluate an importance-weighted marked Hawkes policy model in R through
/app/run.sh. Learn held-out event scores and marked excitation from clustered
histories, enforce the joint branching, support, and deletion-stability
constraints, choose the policy under the required tie order, and certify it by
fully refitting every cluster-deletion surface.

Read the input bundle from the first argument, defaulting to /app/data, and
atomically replace the CSV at the second argument, defaulting to
/app/outputs/results.csv. The complete input, validation, numerical, ordering,
deletion-certificate, and audit-signature contract is in
/app/docs/OUTPUT-CONTRACT.md.

Derive every result from the supplied bundle. Hidden bundles vary identifiers,
marked-event geometry, time scales, overlap, feasibility boundaries,
influential clusters, and physical row and column order. Valid results must be
deterministic and invariant to irrelevant representations. Malformed bundles
must be rejected without replacing prior output. Internet access is
unavailable; only base R is guaranteed.
