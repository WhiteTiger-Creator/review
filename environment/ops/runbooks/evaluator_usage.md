# Ceremony trust notes

Working tree is `/app`. Deep admission is the trust authority for recovery;
the surface path is triage-only.

| Path | Role |
| --- | --- |
| `/app/bin/jarcheck` | Surface checker (not host authority) |
| `/app/ops/run_mesh.sh` | Publish ceremony ledger + quarantine |
| `/app/data/signed_segments/` | Signed WAL segments |
| `/app/data/credentials/` | Credential JSONL feeds |
| `/app/data/fixtures/` | Surface attestation + audit samples |
| `/app/ops/trust_policy.toml` | Authority class and verification mode |

Do not treat surface OK as deep admit success.
