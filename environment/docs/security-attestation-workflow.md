# Security attestation workflow — trust admission

This workflow is a security attestation and trust-policy enforcement problem focused on cryptographic admission control.

## Threat model

- Tampered corpus bytes after seal must fail digest binding.
- Stale issuer-adjacency witnesses after re-seal must fail attest-chain.
- Cross-signed, expired, name-constrained, and policy-failing peers must not produce a successful attested chain.
- Lexicographically smaller id sequences that fail cryptographic or policy checks must be discarded before selection.

## Trust controls

1. **Seal** — digest-bind the candidate certificate corpus and advance a monotonic seal epoch.
2. **Bind** — seal issuer adjacency as a witness for that binding.
3. **Attest** — verify signatures, temporal windows, pathLen, DNS name constraints, and certificate-policy intersection; emit one attested leaf-to-root id chain or a refusal envelope.

Authoritative contracts for each control live alongside this document under `/app/docs/`.
