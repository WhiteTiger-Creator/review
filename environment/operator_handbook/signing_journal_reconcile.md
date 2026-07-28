# Signing journal reconciliation

The filesystem journal under `access/` carries two record kinds. `ACCESS` lines
feed the provenance join in `access_evidence_join.md`. `SIGN` lines attest that
a custodian signed a certificate fingerprint at a moment in time:

```
SIGN cert_fp=<hex> signer=<id> ts=<RFC3339> record=<id>
```

Reconciliation reads every `SIGN` line from `access/access.journal`. When
`access/held_out.journal` is present beside it, those lines are reconciled too.
Grading may supply additional events of the same schema; line order within either
file is irrelevant.

## Custodian window join

Custodian terms live in `warrants/warrants.db` table `authorized_signer`, not in
the journal. Each row names a `signer_id`, a `role`, and inclusive RFC 3339
bounds `role_from` and `role_until`. Only rows with `role = custodian` participate.

For each `SIGN` event, look up the signer. The event is **`in_window`** when a
custodian row exists and `role_from <= ts <= role_until`. Otherwise it is
**`out_of_window`**. The test uses the event timestamp `ts`, never `eval_time`.

| reconcile_status | meaning |
|------------------|---------|
| `in_window` | signer held custodian at `ts` |
| `out_of_window` | no custodian row, or `ts` outside that row's term |

No single journal line reveals compromise. Each line names an ordinary signer and
timestamp; only joining the full reconciled corpus against the roster shows which
events fall outside the windows that signer held.

## Reconcile key and corpus digest

Per event:

```
reconcile_key = SHA256(cert_fp + ":" + signer_id + ":" + ts)
```

(lowercase hex, 64 characters)

Sort reconciled events by `(cert_fp, signer_id, ts)`. The **journal reconcile
digest** folds the whole corpus:

```
journal_reconcile_digest = SHA256( reconcile_key_1 bytes || reconcile_key_2 || ... )
```

in that sorted order, with no separators between keys.

## Compromised leaves

Map each `cert_fp` to the leaf common name under `leaves/` when one exists.
A leaf is **compromised** when it has at least one `out_of_window` reconciled
event on its fingerprint. Compromised leaves are treated as **`contain`**
subjects when choosing the exposure containment set in `exposure_containment.md`,
even when `exposure.tsv` names them `preserve`. The containment search must cut
every live path for every compromised leaf in addition to the incident list.

## Output artifact

`signing_reconcile.tsv` header:

```
cert_fp	signer_id	event_ts	reconcile_key	reconcile_status
```

Rows are the sorted reconciled events. The receipt records
`journal_reconcile_digest` and `compromised_leaves` (comma-separated common
names, sorted, empty when none).
