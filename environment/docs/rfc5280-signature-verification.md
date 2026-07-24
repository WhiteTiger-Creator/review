# RFC 5280 Signature Verification and Temporal Validity

## 1. Signature Verification

To simulate public key cryptography without requiring external private key files, certificate signatures are verified by checking that the certificate's `signature` field matches the SHA-256 hash of its canonical data appended with the issuer's `public_key`.

A certificate `C` signed by an issuer certificate `I` is valid if:
`C.signature == hex(sha256(canonical_string(C) + I.public_key))`

For trusted root certificates, the certificate is self-signed:
`C.signature == hex(sha256(canonical_string(C) + C.public_key))`

### Canonical String Construction

The canonical string of a certificate is constructed by concatenating the following fields in order, separated by a pipe character (`|`):

1. `id` (e.g. `cert-leaf`)
2. `subject` (e.g. `CN=leaf.example.com`)
3. `issuer` (e.g. `CN=intermediate-ca`)
4. `public_key` (e.g. `pubkey-leaf`)
5. `validity.not_before` (formatted as a decimal integer string, e.g. `1700000000`)
6. `validity.not_after` (formatted as a decimal integer string, e.g. `1800000000`)
7. `is_ca` (either `"true"` or `"false"`; if `basic_constraints` is null, defaults to `"false"`)
8. `path_len_constraint` (the integer value as string, or `"null"` if not specified or basic_constraints is null)
9. `permitted_dns` (the list of permitted DNS strings sorted lexicographically and joined by a comma, or `"null"` if name_constraints is null or permitted_dns is not specified)
10. `excluded_dns` (the list of excluded DNS strings sorted lexicographically and joined by a comma, or `"null"` if name_constraints is null or excluded_dns is not specified)
11. `certificate_policies` (the list of policy OIDs sorted lexicographically and joined by a comma, or `"null"` if not specified)
12. `require_explicit_policy` (the integer value as string, or `"null"` if policy_constraints is null or require_explicit_policy is not specified)

Pool digests for trust binding use each certificate's `canonical_string` representation (see above), hashed in ascending `id` order with a single newline byte after each entry.

## 2. Temporal Validity Check

For every certificate `C` in the admitted chain, the validation time `T` must fall within its validity window:
`C.validity.not_before <= T <= C.validity.not_after`
