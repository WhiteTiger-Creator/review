# Access evidence join

Filesystem journal (`access/access.journal`) lines:

```
ACCESS cert_fp=<hex> service=<id> ts=<RFC3339> record=<id> bytes=<n>
```

SQLite mirror: `access/access_audit.db` table `access_records`.

Join bucket key: `(cert_fp, service_id, access_minute)` where `access_minute`
is the first 16 characters of `access_ts` (`YYYY-MM-DDTHH:MM`).

Join digest:

```
SHA256(cert_fp + ":" + service_id + ":" + access_minute)
```

(lowercase hex, 64 chars)

| status | meaning |
|--------|---------|
| `joined` | tuple in both journal and DB |
| `fs_only` | journal only |
| `db_only` | DB only |

Output `access_evidence.tsv` header:

```
cert_fp	service_id	access_minute	join_key	join_status
```

Rows sorted by `(cert_fp, service_id, access_minute)`.

Journal line order is irrelevant.
