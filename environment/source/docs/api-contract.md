# Attestation API contract

`POST /api/v1/attestations` accepts multipart `archive` (uncompressed tar) and optional `release_ref`.

Successful responses include `schema_version`, `archive_sha256`, `baseline`, `verdict`, `findings`, and `signature`.
