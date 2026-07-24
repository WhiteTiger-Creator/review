# Trust Admission Attestation Overview

Task identity 59cebf22ed governs cryptographic trust-admission for a zero-trust gateway. The admission controller must enforce RFC 5280 signature verification, certificate-policy intersection, DNS name-constraint enforcement, and trusted-root anchor binding before emitting a single attested leaf-to-root identity chain—or a cryptographic refusal envelope.

Authoritative contracts live only under `/app/docs/`. Packages under `src/decoy_policy/`, `src/decoy_nc/`, and `src/decoy_lex/` are non-authoritative decoys.

## Admission utility

Primary binary: `/app/bin/trustadmit` (release artifact at `/app/target/release/trustadmit` before install).

| Path | Role |
|------|------|
| `/app/data/pool.json` | Bundled candidate certificate corpus |
| `/app/data/roots.json` | Bundled trusted root anchor ids |
| `/app/state/trust_bind.json` | Default trust binding when no explicit `--binding` path is given |
| `/app/state/seal_epoch.json` | Monotonic seal-epoch ledger |
| `/app/state/.trustadmit_ready` | Seal-corpus ready latch required before attest-chain |
| `/app/state/issuer_adjacency.json` | Sealed issuer adjacency index |
| `/app/bin/trustadmit` | Trust-admission attestation binary |

## Attestation verbs

1. `trustadmit seal-corpus --pool POOL --binding BINDING` — seal corpus digest and advance seal epoch (`/app/docs/trusted-root-anchor-binding.md`).
2. `trustadmit bind-issuers --binding BINDING` — seal issuer adjacency for the binding (`/app/docs/issuer-adjacency-seal.md`).
3. `trustadmit attest-chain --binding BINDING --roots ROOTS --target TARGET --time TIME --output OUT` — verify binding, adjacency, and RFC 5280 constraints; emit chain or refusal (`/app/docs/attestation-refusal-envelope.md`).

`attest-chain` never accepts `--pool`; it loads the corpus only through the sealed binding.

Cross-contract index: signature `/app/docs/rfc5280-signature-verification.md`; policy `/app/docs/certificate-policy-intersection.md`; DNS NC `/app/docs/dns-name-constraint-enforcement.md`; pathLen `/app/docs/pathlen-security-bound.md`; chain selection `/app/docs/attested-chain-selection.md`.
