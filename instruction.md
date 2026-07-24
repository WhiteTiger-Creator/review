We gate every release behind threshold co-signing: it ships only when a quorum
of enrolled signers co-signed it with valid keyed tags whose aggregate
reconstructs correctly. Build a Java audit tool that reads one append-only
release ledger — enrollments, removals, key rotations, anchor/vouch trust
designations, releases, cosignatures, authorization queries — and renders a
k-of-n verdict per query. This is a co-signing authorization control, not a
tally or voting exercise.

Each keyed tag is a hand-rolled MAC and each aggregate an order-dependent
combine of signer tags, both bit-exact on the JDK standard library alone, no
`javax.crypto`, no third-party jar, offline at `/app/audit` on the ledger
path. Write one JSON line to `/app/output/result.json` and print it.

A verdict draws only on ledger state above its query: active roster, each
signer's key in force, cosignatures verified under that key. Removal drops a
signer; rotation voids that signer's earlier cosignatures. When the ledger
names any anchors, a cosignature also needs its signer currently in
*standing*: permanent for active anchors, earned by anyone else only through
two distinct already-standing vouchers — a ring vouching solely for itself
never bootstraps standing without a path back to an anchor. Authorized needs
threshold-met cosigners and a matching aggregate; short is unauthorized, met
but mismatched is tag_mismatch. Full grammar, MAC, combine, roster/rotation/
standing rules, schema, exit codes, and precedence are in `/app/SPEC.md` with
worked vectors.
