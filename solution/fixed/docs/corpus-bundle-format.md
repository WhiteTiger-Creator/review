# Corpus bundle format

Each release commit contains `release.json` with:

- `schema_version` (integer)
- `policy_path` (relative path to hydrated YAML policy)
- `policy_sha256` (sha256 hex digest of hydrated policy bytes)

Policy YAML defines secret patterns, compose rules, PEM thresholds, JWT rules, and text rules.
