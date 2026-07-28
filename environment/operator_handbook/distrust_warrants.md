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

`authorized_signer` is the endorsement roster. Besides `signer_id` and `role` it
carries `role_from` and `role_until`, the inclusive RFC 3339 bounds of the term
during which that signer held that role. Roles are appointed and they lapse, so
the roster is a history rather than a snapshot of who is a custodian today.

## When a warrant is honoured

A warrant takes effect only when **all** of these hold. They are independent
conditions on a single warrant, so they can be checked in any order and the
result never depends on which warrant you look at first.

1. `target_kind` is one of the two documented kinds.
2. `not_before <= eval_time <= not_after`, where `eval_time` comes from
   `eval_time.txt`. Both bounds are inclusive.
3. The number of **distinct** signers with a counting endorsement is at least
   `warrant_quorum` from the `[remediation]` section of the policy. An
   endorsement counts when the signer is rostered with role `custodian` and its
   `signed_at` falls within that roster row's `role_from`/`role_until` term,
   inclusive on both bounds. Repeated rows from one custodian are one
   endorsement. Signers missing from the roster, rostered under any other role,
   or endorsing outside their own term contribute nothing.

   Note that the term is tested against `signed_at`, not against `eval_time`.
   Condition 2 asks whether the warrant is live now; condition 3 asks whether
   each signer was a custodian back when they signed. A custodian appointed
   after they endorsed, or whose term lapsed before they endorsed, does not
   count even though they are rostered as a custodian at `eval_time`.
4. No row in `warrant_countermand` names the warrant.
5. `issuer_cn` matches the subject common name of a certificate under
   `authorities/`, and that authority is not under cascaded distrust as defined
   in `authority_cascade.md`. An authority that is distrusted by name, or that
   sits anywhere beneath one, cannot authorise further distrust.

Condition 5 reads the distrust tables **as the migration left them**. Honouring
a warrant never changes whether some other warrant is honourable, and the
cascade is computed once from post-migration name distrust rather than from the
patch being built.

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
