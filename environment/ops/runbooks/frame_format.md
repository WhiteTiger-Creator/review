# WAL segment frame layout

Segments under `/app/data/signed_segments/` contain concatenated frames:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | magic `0xA5` |
| 1 | 1 | lane id (see `/app/ops/trust_policy.toml` `[lanes]`) |
| 2 | 2 | epoch id, big-endian |
| 4 | 2 | payload length, big-endian |
| 6 | N | payload text (`ts=<u64>;hold=<0|1>;tag=<id>`) |
| 6+N | 64 | signature trailer |

The signed message is not the bare payload alone — pre-incident samples under
`/app/data/fixtures/` show `message_hex` alongside `payload` for working frames.
Segment files are read in filesystem name order; deep attestation then interleaves
integrity-accepted WAL frames with credential JSONL frames by ascending timestamp
within each epoch-and-lane stream before the monotonic replay check. Quarantine is
published beside the attestation output.
