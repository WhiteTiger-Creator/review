# Restore OIDC gateway trust after mTLS policy migration failure

An offline security migration service under `/app/environment` converts a legacy mutual-TLS service call graph, authorization YAML, and security decision corpus into an OIDC gateway policy bundle plus SQLite audit evidence. A partial cutover left trust-boundary enforcement broken: unsafe JWKS material can be accepted, semantic issuer URLs are replaced with hardcoded values, transport fixture hosts leak into policy, parallel edges collapse, dossier authority is ignored, explicit denies are bypassed, and recursive coverage checks are skipped.

Recover gateway trust by repairing verifier logic under `/app/environment`. Static output writes or verifier edits are insufficient; the migrator binary must regenerate policy and audit artifacts through the normal pipeline.

After `/app/environment/bin/reset-state`, this command must exit zero from working directory `/app`:

```bash
/app/environment/bin/migrate-policy
```

Inputs live under `/app/environment/input` and `/app/environment/dossier`. Identity-provider metadata must be obtained through the configured offline transport. Effective policy must record semantic issuer URLs from bundled discovery documents, not loopback fixture hosts.

## Trust and security requirements

- Retire all mTLS-only certificate fields (`client_cert_subject`, `ca_bundle`, `serial_number`, `mtls_trust_bundle`) from emitted gateway policy.
- JWKS ingestion must reject symmetric algorithms, `none`, encryption-only keys, and keys without verify operations.
- Policy issuers must match bundled semantic discovery URLs; hardcoded or transport-derived issuer values are invalid.
- Parallel graph edges with distinct environment, method, path, or authz_scope must remain distinct in policy output.
- Dossier authority rules under `/data/dossier-authority` govern which decision statuses and scopes are authoritative.
- Superseded and proposed dossier entries must not override accepted or amended audience decisions.
- Explicit deny edges such as `api-gateway` to `payment-service` must remain `action: deny`.
- Retired service `admin-api` must not appear with `action: allow`.
- Recursive audit view `coverage_gaps` must be empty and `latest_complete_run.status` must be `COMPLETE`.
- Re-running migration must be idempotent and produce byte-identical `/output/gateway-policy.yaml`.
- Protected trees under `/data/canonical`, `/data/oidc-contracts`, and `/data/dossier-authority` must remain unchanged.

Write `/output/gateway-policy.yaml`, `/output/migration-summary.json`, and `/output/migration-audit.db`. The migration-contract at `/app/environment/docs/migration-contract.md` documents required `schema_version`, issuers, edges, edge `action`, `jwks_uri`, `run_id`, `edge_count`, and `status` fields.

Grading uses Python's `sqlite3` module against `/output/migration-audit.db` and PyYAML against `/output/gateway-policy.yaml`, running `python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py` after reset. Do not modify `/tests`.
