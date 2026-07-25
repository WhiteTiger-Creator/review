# Distrust warrants

`warrants/warrants.db` holds the standing authorisations to put a certificate
back under distrust after the migration dropped rows. A warrant is a statement,
not an event: it has no position in a timeline and nothing accumulates from one
warrant to the next. Each is judged on its own merits against the store as the
migration left it.

## Tables

`distrust_warrant`

| column | meaning |
|--------|---------|
| `warrant_id` | stable identifier |
| `target_kind` | `fingerprint` or `common_name` |
| `target_value` | the fingerprint or CN to distrust |
| `issuer_cn` | common name of the authority that raised the warrant |
| `not_before`, `not_after` | inclusive validity window, RFC 3339 in UTC |
| `justification` | free text for the operator record |

`warrant_countersignature` pairs a `warrant_id` with a `signer_id` and the time
that signer endorsed it. A signer may appear more than once for the same
warrant; those rows are the same endorsement recorded twice.

`warrant_countermand` names warrants that were withdrawn after issue.

`authorized_signer` is the endorsement roster: a `signer_id` and its `role`.

## When a warrant is honoured

A warrant takes effect only when **all** of these hold. They are independent
conditions on a single warrant, so they can be checked in any order and the
result never depends on which warrant you look at first.

1. `target_kind` is one of the two documented kinds.
2. `not_before <= eval_time <= not_after`, where `eval_time` comes from
   `eval_time.txt`. Both bounds are inclusive.
3. The number of **distinct** signers that endorsed the warrant **and** carry
   role `custodian` in `authorized_signer` is at least `warrant_quorum` from the
   `[remediation]` section of the policy. Repeated rows from one custodian are
   one endorsement. Signers missing from the roster, or rostered under any other
   role, contribute nothing.
4. No row in `warrant_countermand` names the warrant.
5. `issuer_cn` matches the subject common name of a certificate under
   `authorities/`, and does not appear in the `distrust_name` table of the
   post-migration store. An authority already distrusted by name cannot
   authorise further distrust.

Condition 5 reads the distrust tables **as the migration left them**. Honouring
a warrant never changes whether some other warrant is honourable.

A warrant failing any condition is **inert**: it contributes no distrust, no
statement in `remediation.sql`, and no row anywhere in the output.

## Effect of an honoured warrant

| `target_kind` | statement added to `remediation.sql` |
|---------------|--------------------------------------|
| `fingerprint` | `INSERT OR IGNORE INTO distrust_fingerprint (fingerprint, source) VALUES ('<target_value>', 'warrant_honored');` |
| `common_name` | `INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('<target_value>', 'warrant_honored');` |

Statements appear in ascending `warrant_id` order beneath the
`-- trust store remediation patch` header, so the patch is byte-stable across
runs regardless of the order rows come back from SQLite.

A fingerprint that is absent from post-migration distrust but restored by an
honoured warrant is a **recovered fingerprint** and is listed in
`audit_receipt.txt`.

`remediation.sql` must be idempotent: applying it twice to a copy of the
post-migration store leaves the distrust tables exactly as one application does.
