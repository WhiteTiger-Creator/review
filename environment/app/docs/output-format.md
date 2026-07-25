# Output format

## Accepted job records

For each accepted job, write:

```text
/output/signed/jobs/<job_id>.json
```

JSON schema:

```json
{
  "schema_version": 1,
  "job_id": "release-2026-001",
  "payload_sha256": "64 lowercase hexadecimal characters",
  "key": "release-primary",
  "key_uri": "canonical PKCS #11 URI or canonical legacy selector representation",
  "key_fingerprint_sha256": "64 lowercase hexadecimal characters",
  "mechanism": "rsa-pss-sha256",
  "signature_base64": "standard base64 without line wrapping",
  "status": "signed"
}
```

## Index

Also write:

```text
/output/signed/index.json
```

Index schema:

```json
{
  "schema_version": 1,
  "jobs": [
    {
      "job_id": "release-2026-001",
      "record": "jobs/release-2026-001.json",
      "payload_sha256": "64 lowercase hexadecimal characters",
      "key_fingerprint_sha256": "64 lowercase hexadecimal characters"
    }
  ]
}
```

## Rules

- `jobs` is sorted by `job_id` using bytewise ascending order.
- Each accepted `job_id` appears exactly once.
- Every index record points to an existing accepted job file.
- Every accepted job file appears exactly once in the index.
- Job JSON is canonical: UTF-8, one trailing newline, sorted object keys, no insignificant whitespace.
- Index JSON uses the same canonical encoding.
- `key_fingerprint_sha256` is SHA-256 over the DER SubjectPublicKeyInfo bytes of the configured public key for the selected logical key.
- `signature_base64` is derived from the token signature (standard Base64, no line wrapping).
- For current-format keys, `key_uri` is the canonical PKCS #11 URI representation of the selected object.
- For legacy-format keys, `key_uri` is the canonical legacy selector representation `legacy:token=<token_label>;object=<key_label>`.
- A rejected job must not have a job file or index entry.
- Publication must never expose a temporary file as a successful job record.
- Existing successful records are stable across another restart.
- A valid final record under `jobs/` that is absent from `index.json` must be kept and restored into a consistent index on the next `run`, even when the journal is empty and there is no staged entry. Missing index membership alone is not a conflict and is not grounds to discard or re-sign that final.
