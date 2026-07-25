# Verifier contract notes

These notes document externally exercised harness details that complement `instruction.md`.

- Hidden corpus remotes include `trusted_a` and `trusted_b` variants with distinct policy bundles and signer fingerprints.
- Branch-style release inputs use a `branch_ref` such as `refs/heads/corpus-v1.0.0` and must be refused.
- `CORPUS_ALLOWED_SIGNER` overrides the configured allowed signer fingerprint for alternate trusted corpora.
- The `signature` object uses `alg`, `key_id`, and `value` fields; `value` holds the base64url signature bytes.
- Verifier-built tar archives use deterministic entry metadata, including mtime `1718452800`, and injection specs name member `data` and archive `name` fields.
- Hidden fixture archives are opened with tar mode `r:` when unpacking Git corpus bundles.
- Platform verification runs `pytest` with reporting flags such as `--confcutdir`, `--ctrf`, `--format`, and `git config --global --add`.
- The verifier reruns `bundle exec rspec --format progress environment/source/spec` against the Rails tree and uses Python `support.*` harness modules (`archive_factory`, `corpus_fixture`, `integrity`, `puma_server`, `signature_checks`) plus `requests` and `__future__` annotations for HTTP checks.
- JSON `findings` is an array of finding objects; canonical signing helpers treat list-valued fields as ordered arrays.
