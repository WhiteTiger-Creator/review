# Policy bootstrap notes

Active `config/signing-policy.yaml` was removed during INF-4412.

Recover policy bytes from local reflogs and unreachable objects using the
GraphRunSigner operations manual roster rules (approval metadata, policy window,
and signing-key constraints). Candidate snapshots may also appear under
`../lost-policy-candidates/` for cross-checking.
