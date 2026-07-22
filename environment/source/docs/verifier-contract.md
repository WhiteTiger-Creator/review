# Verifier contract notes

These notes document externally exercised harness details that complement `instruction.md`.

- Hidden corpus remotes include `trusted-corpus-a`, `trusted-corpus-b`, and `untrusted-signer-corpus` variants with distinct policy bundles and signer fingerprints. Verifier metadata keys `trusted_a`, `trusted_b`, `unsigned`, and `untrusted` describe each corpus profile in `corpus_metadata.json`.
- Branch-style release inputs use a `branch_ref` such as `refs/heads/corpus-v1.0.0` and must be refused.
- `CORPUS_ALLOWED_SIGNER` overrides the configured allowed signer fingerprint for alternate trusted corpora.
- The `signature` object uses `alg`, `key_id`, and `value` fields; `value` holds the base64url signature bytes.
- Verifier-built tar archives use deterministic entry metadata, including mtime `1718452800`, and injection specs name member `data`, archive `name`, and `path` fields such as `stack/docker-compose.yml`.
- Multipart uploads use `application/x-tar` for the archive field.
- Hidden fixture archives are opened with tar mode `r:` when unpacking Git corpus bundles.
- Platform verification runs `pytest` with `PYTHONSAFEPATH=1` and reporting flags such as `--confcutdir`, `--ctrf`, `--format`, and `git config --global --add`. Oracle smoke checks may track a background Puma `PUMA_PID` for cleanup.
- The verifier reruns `bundle exec rspec --format progress /app/environment/source/spec` against the Rails tree and uses Python `support.*` harness modules (`archive_factory`, `corpus_fixture`, `integrity`, `puma_server`, `signature_checks`) plus `requests`, `hashlib`, `random`, `signal`, `tarfile`, `zstandard`, `base64`, and `__future__` for HTTP and archive checks.
- JSON `findings` is an array of finding objects; canonical signing helpers treat list-valued fields as ordered arrays.
- Signature verification reads `attestor-public.pem`, `corpus_metadata.json`, and `fixture-checksums.json`; OpenSSL verify uses `payload.bin` and `signature.bin` scratch files.
- Injection scenarios may include `CORPUS-B-VAULT-LINE`, `CORPUS_CACHE_ROOT`, `CORPUS_REMOTE_URL`, `jwt.forbidden_algorithm`, and `sk_live_abcdefghijklmnop` markers.
- Example injected archive lines exercised by the verifier:

```
corp_b_vault_marker
PUBLIC_URL=https://example.com
API_SECRET=sk_live_qwertyuiopasdfgh
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhYmMifQ.
```
