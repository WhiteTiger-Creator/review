# Remediation output artifacts

On success the utility writes under the output directory:

| file | description |
|------|-------------|
| `remediated_trust_store.db` | copy of incident store with patch applied |
| `remediation.sql` | idempotent INSERT OR IGNORE statements |
| `remediated.policy` | line-preserving policy copy |
| `access_evidence.tsv` | joined provenance rows |
| `signing_reconcile.tsv` | custodian-window reconciliation for every SIGN line |
| `certificate_decisions.tsv` | leaf validation results |
| `audit_receipt.txt` | key=value summary |

Receipt keys, one per line as `key=value`, in this order:

- `warrants_honored` — count of warrants that satisfied every condition
- `warrants_inert` — count that failed at least one. Together with
  `warrants_honored` this accounts for every row in `distrust_warrant`.
- `restored_fingerprints` (comma-separated, sorted, empty if none)
- `containment_names` — the containment set of `exposure_containment.md`,
  comma-separated, sorted, empty if the incident needed no cut
- `containment_size` — how many names that is
- `journal_reconcile_digest` — fold over every reconciled SIGN event; see
  `signing_journal_reconcile.md`
- `compromised_leaves` — comma-separated compromised leaf common names, sorted,
  empty when none
- `artifact_digest`

`artifact_digest` = SHA256 hex of the concatenation, in order, of file contents:
`remediation.sql`, `access_evidence.tsv`, `signing_reconcile.tsv`,
`certificate_decisions.tsv` (no extra separators).

All TSV files use tab separators, LF line endings, header row, no trailing blank
line after the last data row.
