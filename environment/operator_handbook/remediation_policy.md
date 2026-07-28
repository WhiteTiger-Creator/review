# Remediation policy round-trip

`remediation.policy` uses INI-like sections. Known fields in `[remediation]`:

- `min_chain_depth` (integer)
- `max_chain_depth` (integer)
- `warrant_quorum` (integer) — how many distinct custodian endorsements a
  distrust warrant needs before it can be honoured

All other sections and keys are **unknown** and must appear byte-identical in
`remediated.policy` on success.

When `min_chain_depth > max_chain_depth`, write only `remediated.policy` with an
appended audit trailer:

```
[remediation_audit]
status=rejected
reason=contradictory_known_fields
```

Exit non-zero. Do not emit SQL, DB, TSV, or receipt artifacts.
