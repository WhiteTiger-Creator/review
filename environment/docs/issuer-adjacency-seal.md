# Issuer Adjacency Seal

After seal-corpus binds a corpus digest and epoch, operators must **bind issuers** into a sealed issuer adjacency index before trust-admission attestation. Attest-chain refuses to run against an absent, stale, or digest-mismatched adjacency seal.

## Subcommand

`trustadmit bind-issuers --binding BINDING_PATH`

1. Load the binding and verify it against `/app/state/seal_epoch.json` (epoch and `pool_digest`).
2. Reload the pool through the binding and recompute `pool_digest` (same algorithm as seal-corpus).
3. Build an issuer adjacency map:
   - For every certificate in the pool, group certificate `id` values by that certificate's `subject` DN.
   - Within each subject group, sort certificate ids in ascending lexicographic order.
4. Write `/app/state/issuer_adjacency.json` (see schema below).

## Adjacency JSON Schema

```json
{
  "fold_epoch": 1,
  "pool_digest": "<hex sha256>",
  "fold_digest": "<hex sha256>",
  "edges": {
    "CN=Example Subject": ["cert-a", "cert-b"]
  }
}
```

Rules:
- `fold_epoch` must equal the binding's `ingest_epoch` and the ledger epoch.
- `pool_digest` must equal the binding and ledger digest.
- `edges` maps each distinct `subject` string to the sorted list of certificate ids that assert that subject.
- Re-sealing a corpus advances the ledger epoch; a previously written adjacency with an older `fold_epoch` must be rejected by attest-chain.

## Adjacency Digest Algorithm

Concatenate, in ascending subject-key order:

1. The subject DN string, then a single newline.
2. Each certificate id in that subject's list (already sorted), each followed by a newline.
3. An extra newline after the last id of that subject (blank line separator between subjects).

`fold_digest` is the lowercase hexadecimal SHA-256 of those concatenated bytes.

## Attest-Chain Requirements

Before attesting a chain, `trustadmit attest-chain` must:

1. Require `/app/state/issuer_adjacency.json` to exist.
2. Verify `fold_epoch` and `pool_digest` match the binding (and therefore the ledger).
3. Recompute `fold_digest` from the on-disk `edges` map and reject mismatches.
4. Expand issuer candidates **only** through the adjacency edges: for the current certificate, look up `edges[current.issuer]` and resolve those ids in the pool. Scanning the pool for `subject == issuer` without consulting the adjacency seal is incorrect.

Chain validation, temporal checks, and lexicographic selection among valid chains remain governed by the other `/app/docs/` contracts.
