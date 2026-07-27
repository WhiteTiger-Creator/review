# Migration contract

The migration writes `/output/gateway-policy.yaml`,
`/output/migration-summary.json`, and
`/output/migration-audit.db`.

## Migration summary

`migration-summary.json` uses schema version `1` and contains:

- `schema_version`: integer `1`
- `run_id`: the positive audit migration-run identifier
- `edge_count`: the number of entries emitted in
  `gateway-policy.yaml` under `edges`
- `status`: the lowercase string `"complete"`
- `revision`: the selected bundled OIDC contract revision

The summary status is intentionally lowercase. It is distinct from
the SQLite audit view `latest_complete_run.status`, whose completed
value is the uppercase string `"COMPLETE"`.

## Gateway policy

`gateway-policy.yaml` uses schema version `2`.

Its `issuers` mapping is keyed by semantic issuer URL. Each issuer
block records:

- `issuer`: the same semantic issuer URL
- `jwks_uri`: the semantic JWKS URI from the selected bundled
  discovery document, never the loopback transport or fetch URL
- `algorithms`: the accepted asymmetric verification algorithms

For `google-revision-a`, the semantic issuer is
`https://accounts.google.com` and the semantic JWKS URI is
`https://www.googleapis.com/oauth2/v3/certs`.

For `google-revision-b`, the semantic issuer remains
`https://accounts.google.com` and the semantic JWKS URI is
`https://www.googleapis.com/oauth2/v3/certs-rotated`.

Each policy edge records its identity and authorization dimensions:

- `edge_id`
- `source`
- `target`
- `environment`
- `method`
- `path`
- `authz_scope`
- `action`

`action` is exactly `allow` or `deny`. Allowed edges additionally
carry the applicable semantic issuer, semantic `jwks_uri`,
audiences, algorithms, allowed key identifiers when present, and
provenance. Explicitly denied edges remain represented with
`action: deny`.

Parallel edges remain separate when any identity or authorization
dimension differs.

## Audit database

`migration-audit.db` stores the migration run and its graph,
discovery, key, decision, and emitted-policy evidence.

The summary `run_id` identifies the corresponding audit run.
A successfully completed authoritative run appears in
`latest_complete_run` with status `"COMPLETE"`. The recursive
`coverage_gaps` view must contain no uncovered deployable edge for
that run.
