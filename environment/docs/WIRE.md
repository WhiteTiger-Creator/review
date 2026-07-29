# Wire notes (draft)

Frames begin with the four-byte magic `K7FR` followed by a big-endian body length and TLV body.

Alternate name TLVs use tag `0x10` and `0x11` (see `internal/model` constants). Ingestion must agree with the offline probe on canonical stamps.

Draft note (may be stale): scope labels follow the **first** alternate TLV in wire order.

Filler TLV tag `0x00` may appear in captured bytes.

## Offline probe

`/opt/k7probe/dy observe --chunk <path>` prints one JSON object with `canon_hex` (lowercase hex digest of the canonical frame stamp) and `body_len` (integer TLV body length). Trailing filler bytes on a capture file must not change `canon_hex` when the logical frame is unchanged.
