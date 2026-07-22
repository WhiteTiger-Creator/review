# Corpus bundle format

Each release commit contains `release.json` with:

- `schema_version` (integer)
- `policy_path` (relative path to hydrated YAML policy)
- `policy_sha256` (hex digest of hydrated policy bytes)

Policy YAML defines secret patterns, compose rules, PEM thresholds, JWT rules, and text rules.

## Attestation response

Successful `POST /api/v1/attestations` returns HTTP 200 with a compact JSON object containing:

- `schema_version`
- `archive_sha256`
- `baseline` with `ref`, `tag_object`, `commit`, `signer_fingerprint`, and `policy_sha256`
- `verdict` (`pass` or `reject`)
- `findings` as a JSON array; each finding has `path`, `kind`, `rule_id`, `severity`, `line`, and `evidence_sha256`
- `signature` as an object with `alg` (`RS256`), `key_id`, and `value` (base64url-encoded signature bytes over the unsigned payload)

The unsigned payload uses recursively key-sorted compact JSON. Error responses use `{"error":{"code":...,"message":...}}`.
