# Trust store database

`trust_store.db` tables:

| table | columns |
|-------|---------|
| `trusted_roots` | `fingerprint` |
| `distrust_fingerprint` | `fingerprint`, `source` |
| `distrust_name` | `common_name`, `source` |
| `store_meta` | `key`, `value` |

Post-migration rows carry `source='post_migration'`. Rows added by an honoured
warrant carry `source='warrant_honored'`.

Remediation copies the file to `remediated_trust_store.db` and applies
`remediation.sql`. The source database under the incident directory is never
modified.
