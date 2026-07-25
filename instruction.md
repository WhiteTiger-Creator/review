# Trust-store remediation incident

Anchor deduplication during a trust-store migration silently dropped
fingerprint-only distrust rows. Standing distrust warrants still authorise those
rows, so the live store currently trusts certificates that operators had already
rejected. The Go utility that is supposed to close the gap, at
`/app/trust-remediator/`, produces incomplete patches and the wrong certificate
verdicts as a result.

Fix it, and leave `/app/data` byte-for-byte as you found it.

Build with the shipped `Makefile`, which links `build/trust_attest`, then run:

    /app/trust-remediator/build/trust_attest --incident /app/data --write /app/output

The incident bundle holds the post-migration store `/app/data/trust_store.db`,
the warrant database `/app/data/warrants/warrants.db`, the policy at
`/app/data/remediation.policy`, the access journal
`/app/data/access/access.journal` beside its SQLite mirror
`/app/data/access/access_audit.db`, the evaluation timestamp in
`/app/data/eval_time.txt`, and PEM material under `/app/data/authorities/` and
`/app/data/leaves/`. `/app/operator_handbook/` documents each of those, the rules
for honouring a warrant, and the exact shape of every artifact. Nothing about the
expected behaviour lives outside that handbook.

Six artifacts belong under `/app/output` on a successful run:
`remediated_trust_store.db`, `remediation.sql`, `remediated.policy`,
`access_evidence.tsv`, `certificate_decisions.tsv`, and `audit_receipt.txt`.

One input can stop the run: if the policy's known chain-depth bounds contradict
each other, exit non-zero having written only `remediated.policy` with its
rejection trailer, and no database, patch, TSV, or receipt.

The rebuilt binary must be newer than every source under `/app/trust-remediator/`
so a stale artifact cannot be graded in place of your work. Both the Go toolchain
and the runtime dependencies are already present system-wide; the build needs no
network access.
