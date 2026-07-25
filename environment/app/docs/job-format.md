# Job format

Each queue file under the configured `queue_dir` is a single JSON object.

## Schema

```json
{
  "schema_version": 1,
  "job_id": "release-2026-001",
  "payload_path": "/app/payloads/release-2026-001.bin",
  "payload_sha256": "64 lowercase hexadecimal characters",
  "key": "release-primary",
  "mechanism": "rsa-pss-sha256"
}
```

## Field rules

- `schema_version` must be the integer `1`.
- `job_id` is a non-empty ASCII identifier matching `[A-Za-z0-9._-]{1,96}`.
- `payload_path` must be an absolute path below `/app/payloads`.
- `payload_sha256` is the expected SHA-256 of the payload bytes, encoded as 64 lowercase hexadecimal characters.
- `key` names a logical key entry from the active service configuration.
- `mechanism` is either `rsa-pss-sha256` or `rsa-pkcs1-sha256`.
- Unknown fields are rejected.

## Canonical job identity

The canonical job body is the canonical JSON encoding of these fields only:

- `schema_version`
- `job_id`
- `payload_path`
- `payload_sha256`
- `key`
- `mechanism`

Canonical JSON means UTF-8, sorted object keys, no insignificant whitespace, and exactly one trailing newline. The canonical job-body digest is SHA-256 over those bytes.

- File name is not part of job identity.
- JSON property order in the queue file is not part of job identity.
- Whitespace in the queue file is not part of job identity.
- A second queue file with the same `job_id` and the same canonical body is idempotent.
- A second queue file with the same `job_id` and a different canonical body is a conflict.
- A pre-existing accepted output record must match the canonical job body before it is treated as already complete.

Queue enumeration order is lexical by file name. Correctness must not depend on the order in which files were created.

## Mechanisms

Supported mechanism strings:

- `rsa-pss-sha256`
- `rsa-pkcs1-sha256`

For `rsa-pss-sha256`:

- hash: SHA-256
- mask generation: MGF1 with SHA-256
- salt length: 32 bytes
- input to the token operation: payload bytes through the selected combined hash-and-sign mechanism

Unknown mechanism strings, mechanisms unsupported by the selected token, key types incompatible with the requested mechanism, and invalid mechanism parameters are rejected.
