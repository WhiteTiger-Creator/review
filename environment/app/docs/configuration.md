# Configuration

The service accepts two configuration generations.

## Current format (`schema_version = 2`)

```toml
schema_version = 2
module = "/usr/lib/softhsm/libsofthsm2.so"
pin_file = "/app/config/token-user.pin"
state_dir = "/app/state"
queue_dir = "/app/queue"
payload_root = "/app/payloads"
output_dir = "/output/signed"
log_dir = "/var/log/signing"
max_jobs_per_worker = 1

[keys.release-primary]
uri = "pkcs11:token=release-token;serial=1001;object=release-signing;type=private;id=%01"
public_key = "/app/config/public/release-primary.pem"

[keys.release-secondary]
uri = "pkcs11:token=release-token;serial=1001;object=release-signing;type=private;id=%02"
public_key = "/app/config/public/release-secondary.pem"
```

Rules:

- `schema_version` is `2`.
- `module`, `pin_file`, and all directory paths are absolute.
- Each current-format key uses a PKCS #11 URI.
- A URI must identify exactly one compatible private key.
- Token label alone is not sufficient when multiple matching tokens or objects exist.
- The configured public key must match the selected private key.
- `max_jobs_per_worker` is a positive integer. The supplied current configuration uses `1` so ordinary processing replaces workers between jobs.

## Legacy format (`schema_version = 1`)

```toml
schema_version = 1
module = "/usr/lib/softhsm/libsofthsm2.so"
pin_file = "/app/config/token-user.pin"
token_label = "legacy-token"
key_label = "legacy-signing"
public_key = "/app/config/public/legacy.pem"
state_dir = "/app/state"
queue_dir = "/app/queue"
payload_root = "/app/payloads"
output_dir = "/output/signed"
log_dir = "/var/log/signing"
```

Rules:

- `schema_version` is `1`.
- Legacy selection uses token label and key label.
- Legacy selection is valid only when it identifies exactly one compatible private key.
- Zero matches or multiple matches are configuration errors.
- Legacy support is compatibility behavior and does not weaken current URI matching.
- The supplied legacy fixture is unambiguous.
- An ambiguous legacy token (multiple compatible keys sharing the same token and key labels) must be rejected.

## Secrets

The token PIN is read from `pin_file`. Do not write the PIN into `/output` or `/var/log/signing`. Private key material must remain token-resident and must not be exported into output or logs.
