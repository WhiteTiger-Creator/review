# Trusted Root Anchor Binding and Seal Epoch

The gateway seals candidate certificate corpora before trust-admission attestation. Seal-corpus binds a corpus file on disk to a cryptographic digest and a monotonic seal epoch so later attest-chain steps cannot silently operate on a mutated corpus or a stale binding from an earlier seal.

## Subcommands

1. `trustadmit seal-corpus --pool POOL_PATH --binding BINDING_PATH`
   - Parse the pool JSON array.
   - Compute `pool_digest` (see `/app/docs/rfc5280-signature-verification.md`).
   - Advance the seal-epoch ledger at `/app/state/seal_epoch.json` (epoch increments by one on every successful seal-corpus).
   - Write a binding JSON object to `BINDING_PATH`, including the new `ingest_epoch`.

2. `trustadmit attest-chain --binding BINDING_PATH --roots ROOTS_PATH --target TARGET_ID --time TIMESTAMP --output OUTPUT_PATH`
   - Load the binding JSON.
   - Require the seal-corpus ready marker and verify the binding against `/app/state/seal_epoch.json` (epoch and `pool_digest` must both match).
   - Require a verified issuer adjacency at `/app/state/issuer_adjacency.json` per `/app/docs/issuer-adjacency-seal.md`.
   - Re-open the pool at `binding.pool_path`, parse it, and recompute `pool_digest`.
   - Reject with non-zero exit if the recomputed digest differs from `binding.pool_digest` or if `cert_count` mismatches.
   - Proceed with chain attestation using the loaded pool and adjacency edges.

The attest-chain subcommand does not accept `--pool`; it always loads the corpus through the binding artifact produced by seal-corpus. Operators must run `trustadmit bind-issuers --binding BINDING_PATH` after seal-corpus (and after any re-seal) before attest-chain.

## Runtime Paths

The bundled candidate corpus and trusted roots ship at `/app/data/pool.json` together with `/app/data/roots.json` — successful seal-corpus without an explicit `--binding` writes the default binding to `/app/state/trust_bind.json` as the gateway default. Operators may also pass an explicit binding path (for example under a temporary directory) when sealing successive corpora that advance the ledger epoch.

## Seal-Corpus Ready Marker

Successful seal-corpus writes a one-byte marker file at `/app/state/.trustadmit_ready` before attest-chain may proceed. The attest-chain subcommand must refuse to run when this marker is absent, even if a binding JSON file exists from an earlier session.

## Seal Epoch Ledger

Every successful seal-corpus updates `/app/state/seal_epoch.json`:

```json
{
  "epoch": 3,
  "pool_digest": "<hex sha256>"
}
```

Rules:
- `epoch` starts at 1 on the first seal-corpus in a container and increments by one on each later successful seal-corpus.
- The binding's `ingest_epoch` and `pool_digest` must equal the ledger values at attest-chain time.
- Re-sealing a corpus (even the same bytes) advances the epoch; a previously written binding with an older epoch must be rejected.
- Deleting the ledger without a fresh seal-corpus must cause attest-chain to fail.

## Binding Basenames

Operators commonly use `binding.json` or `trust_bind.json` as binding path basenames when running seal-corpus in temporary directories.

## Binding JSON Schema

```json
{
  "pool_path": "/absolute/or/relative/path/to/pool.json",
  "pool_digest": "<hex sha256>",
  "cert_count": 23,
  "ingest_epoch": 1
}
```

## Pool Digest Algorithm

Pool digests bind seal-corpus output to the canonical certificate material in the pool file. Certificates are hashed in ascending `id` order using each certificate's `canonical_string` representation (see `/app/docs/rfc5280-signature-verification.md`), with a single newline byte after each entry. The digest is the lowercase hexadecimal SHA-256 of the concatenated bytes.

## Failure Semantics

- Missing binding file, malformed binding JSON, digest mismatch, count mismatch, missing/mismatched seal-epoch ledger, or stale `ingest_epoch` → non-zero exit; no chain output.
- Successful chain attestation still writes the chain JSON array to `--output` on exit 0.
