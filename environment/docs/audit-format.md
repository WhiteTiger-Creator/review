# Audit evidence format

The evidence directory contains `pulse-<index>.json` for every index in the inclusive case interval plus `certificate.pem`. Pulse files retain the complete response body from the NIST API. The certificate file retains the complete PEM response for the certificate identifier shared by the interval.

No other directory entries are permitted. The directory and every retained entry must be regular, non-symlinked filesystem objects, and each file is limited to 2 MiB. The case carries one uppercase SHA-512 pin per byte-exact pulse body and one for the PEM certificate response; acquisition and verification both enforce them. JSON inputs contain exactly one value: unknown fields, duplicate object keys at any depth, and trailing values are invalid. Pulse status and external status are zero. Cryptographic hexadecimal strings use uppercase; the pulse `certificateId` may be consistently uppercase or lowercase. `listValues` contains each of `previous`, `hour`, `day`, `month`, and `year` exactly once. Every list URI uses the pulse origin and chain, never points forward, and the `previous` URI names the immediately preceding pulse.

The receipt is UTF-8 JSON with two-space indentation and a trailing newline. Keys appear in schema order. Hexadecimal digests and cryptographic values in the receipt are uppercase. `evidence_sha512` hashes the byte-exact retained file. `signature_verified`, `output_hash_verified`, and `certificate_valid_at_pulse` describe individual pulse checks; chain-wide booleans cover index, timestamp, previous-output, and precommitment continuity. `audited_at` is the newest pulse timestamp, making repeated verification deterministic.

For cipher suite 0, cryptographic verification follows the deployed NIST Beacon 2.0 encoding: integers and field-length prefixes are unsigned 32-bit big-endian values except the chain and pulse indexes, which are unsigned 64-bit big-endian values. Hash fields decode to 64 bytes and the 512-byte signature is appended without a length prefix when recomputing `outputValue`. Hashing uses SHA-512, and signatures use RSA PKCS#1 v1.5 with SHA-512.

The strict policy profile has all five `require_*` checks enabled. Trust certificate IDs are unique canonical uppercase SHA-512 strings. The pinned certificate is a non-CA RSA end-entity certificate with digital-signature key usage and both a matching subject common name and DNS subject alternative name.

On any failure, the command exits nonzero, writes a diagnostic to stderr, and does not leave a new receipt or partial final evidence file. A receipt path is outside the evidence directory, beneath an existing non-symlinked parent, and is not itself a symlink or other special file. Failed verification leaves an existing regular receipt byte-for-byte unchanged.

Acquisition path validation happens before any network request. An unsafe existing destination is diagnosed with the stable reason phrase `not a safe directory`.
