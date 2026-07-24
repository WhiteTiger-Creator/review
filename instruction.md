# Cryptographic trust-admission attestation

Task identity 59cebf22ed governs cryptographic trust-admission attestation under RFC 5280 trust policy for a zero-trust gateway. Client identity caches mix cross-signed intermediates, expired siblings, and name- or policy-constrained peers. Sealed corpus digests, issuer-adjacency witnesses, and attested leaf-to-root identity chains must agree with independent policy checks before admission; otherwise the gateway emits a cryptographic refusal envelope.

Authoritative behavior is defined only by /app/docs/, including /app/docs/security-attestation-workflow.md and /app/docs/trust-admission-attestation.md. Packages under src/decoy_policy/, src/decoy_nc/, and src/decoy_lex/ are non-authoritative decoys.

## Trust-admission problem

Admission control refuses clients whose PKIX chains should still validate under policy. Corpus digests drift after seal-corpus, issuer adjacency seals go stale across re-seal epochs, and tie-breaking among otherwise-valid chains disagrees with /app/docs/attested-chain-selection.md. Temporal windows, basicConstraints pathLen, DNS name constraints, and policy OID intersection must all hold for the admitted chain. Compromise modeling treats a digest-mismatched corpus or a stale adjacency seal as a trust failure, not a soft warning.

## Required capability

Build a new trust-admission attestation workflow under /app that seals corpus digests, binds issuer adjacency witnesses, and emits attested identity chains or refusal envelopes per /app/docs/trustadmit-operator-manual.md. Graded surface: /app/bin/trustadmit. Seal epoch, digest, and anchor rules: /app/docs/trusted-root-anchor-binding.md. Signature and temporal checks: /app/docs/rfc5280-signature-verification.md. Success and refusal JSON shapes: /app/docs/attestation-refusal-envelope.md. Path length: /app/docs/pathlen-security-bound.md. Name and policy rules: /app/docs/dns-name-constraint-enforcement.md and /app/docs/certificate-policy-intersection.md. Chain selection: /app/docs/attested-chain-selection.md. Issuer adjacency seal: /app/docs/issuer-adjacency-seal.md.

Bundled trust material lives at /app/data/pool.json and /app/data/roots.json; default binding is /app/state/trust_bind.json; seal-epoch ledger /app/state/seal_epoch.json; ready latch /app/state/.trustadmit_ready; adjacency witness /app/state/issuer_adjacency.json; non-integer --time values such as invalid-timestamp must be rejected. Unknown targets such as non-existent-leaf must be refused per the attestation envelope contract.
