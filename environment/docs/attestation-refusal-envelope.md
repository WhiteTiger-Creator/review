# Attestation and Refusal Envelope

All certificates in the pool are stored in a single JSON array. Each certificate object contains the following fields:

```json
{
  "id": "cert-identifier",
  "subject": "CN=subject-name",
  "issuer": "CN=issuer-name",
  "public_key": "public-key-hex-string",
  "validity": {
    "not_before": 1700000000,
    "not_after": 1800000000
  },
  "basic_constraints": {
    "is_ca": true,
    "path_len_constraint": 2
  },
  "name_constraints": {
    "permitted_dns": ["example.com"],
    "excluded_dns": ["bad.example.com"]
  },
  "certificate_policies": ["1.2.3.4", "2.5.29.32.0"],
  "policy_constraints": {
    "require_explicit_policy": 1
  },
  "signature": "signature-hex-string"
}
```

### Fields Description

- `id`: A unique string identifying the certificate.
- `subject`: The subject distinguished name.
- `issuer`: The issuer distinguished name.
- `public_key`: A hex-encoded public key representing the certificate holder's key.
- `validity`: Validity period timestamps in Unix epoch seconds.
- `basic_constraints`: Optional object. `is_ca` specifies whether the certificate is a CA. `path_len_constraint` (optional integer) limits the maximum number of non-self-issued intermediate certificates that can follow this certificate in a valid path.
- `name_constraints`: Optional object specifying permitted and/or excluded DNS subtrees.
- `certificate_policies`: Optional array of policy OID strings.
- `policy_constraints`: Optional object. `require_explicit_policy` specifies the number of certificates after which an explicit policy is required.
- `signature`: Hex-encoded signature string.

### Success Envelope

On successful trust admission, write a JSON file containing an array of certificate IDs representing the chain from the target leaf to the root:
```json
["cert-leaf", "cert-intermediate", "cert-root"]
```

### Refusal Envelope

On admission refusal, write a JSON file containing a failure report:
```json
{
  "status": "failed",
  "error": "No valid path found"
}
```
