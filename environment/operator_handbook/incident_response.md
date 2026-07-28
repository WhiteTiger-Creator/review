# Incident response workflow

1. Validate `remediation.policy` bounds; stop early if the known bounds contradict.
2. Load post-migration distrust from `trust_store.db`.
3. Decide each warrant in `warrants/warrants.db` independently, then build
   `remediation.sql` from the honoured ones.
4. Join the access journal with the audit mirror.
5. Reconcile every SIGN line against custodian roster terms, including any
   held-out journal shard grading supplies, and fold the corpus digest.
6. Choose exposure containment using compromised leaves from that reconciliation.
7. Copy the trust store, apply the patch, and validate certificates against the
   remediated distrust set.
8. Emit the artifacts and the receipt digest.

Step 3 is where the store's own contents feed back into the decision: an
authority distrusted by name cannot authorise a warrant, and that is read from
the post-migration tables loaded in step 2, never from the patch being built.

The shipped incident under `/app/data` exercises the whole chain: a fingerprint
recovered from dedup loss, warrants inert for each documented reason, access
evidence that only one of the two sources recorded, and a cross-signed leaf whose
two candidate paths fail differently.
