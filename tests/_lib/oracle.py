"""Independent oracle for the framekit length-underflow audit.

A direct, from-scratch translation of docs/frame-format.md's dispatch and
wrapping-arithmetic contract into Python. It recomputes the verdict for each
case from the raw evidence and is never derived from the candidate's findings.
Kept deliberately self-contained so the verifier owns its own ground truth.
"""

import json
from pathlib import Path

MASK64 = (1 << 64) - 1
HEADER_SIZE = 13
ABSOLUTE_MAX = 1_000_000_000

VERDICTS = (
    "REJECT_MAGIC",
    "REJECT_OUTER_LEN_BOUND",
    "SAFE_NO_UNSAFE_READ",
    "REACHABLE_SAFE",
    "REACHABLE_EXPLOITABLE",
    "MALFORMED",
)


def parse_config(config_text: str):
    """Return (fast_path_compiled, source_variant) or None when malformed."""
    try:
        obj = json.loads(config_text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    fpc = obj.get("fast_path_compiled")
    sv = obj.get("source_variant")
    if not isinstance(fpc, bool):
        return None
    if sv not in ("original", "guarded"):
        return None
    return (fpc, sv)


def decide(buf: bytes, fast_path_compiled: bool, source_variant: str) -> str:
    """Verdict for a frame already known to be at least HEADER_SIZE bytes."""
    if buf[0:4] != b"FK01":
        return "REJECT_MAGIC"
    outer_len = int.from_bytes(buf[4:8], "little")
    sub_len = int.from_bytes(buf[8:12], "little")
    flag_byte = buf[12]
    if outer_len > ABSOLUTE_MAX:
        return "REJECT_OUTER_LEN_BOUND"

    fast_taken = (
        fast_path_compiled and source_variant == "original" and (flag_byte & 1)
    )
    if not fast_taken:
        return "SAFE_NO_UNSAFE_READ"

    payload_len = (outer_len - HEADER_SIZE) & MASK64
    body_len = (payload_len - sub_len) & MASK64
    end = (HEADER_SIZE + body_len) & MASK64

    if end <= len(buf):
        return "REACHABLE_SAFE"
    return f"REACHABLE_EXPLOITABLE:{HEADER_SIZE}-{end}"


def classify(config_text: str, frame: bytes) -> str:
    """Full verdict for one case, including the MALFORMED bucket."""
    cfg = parse_config(config_text)
    if cfg is None:
        return "MALFORMED"
    if len(frame) < HEADER_SIZE:
        return "MALFORMED"
    fast_path_compiled, source_variant = cfg
    return decide(frame, fast_path_compiled, source_variant)


def encode_frame(
    outer_len: int,
    sub_len: int,
    flag_byte: int,
    payload: bytes = b"",
    magic: bytes = b"FK01",
    outer_len_endian: str = "little",
    sub_len_endian: str = "little",
) -> bytes:
    return (
        magic
        + (outer_len & 0xFFFFFFFF).to_bytes(4, outer_len_endian)
        + (sub_len & 0xFFFFFFFF).to_bytes(4, sub_len_endian)
        + bytes([flag_byte & 0xFF])
        + payload
    )


def load_cases(path) -> list[dict]:
    """Read a cases manifest: one JSON object per line with id, config_text, frame_hex."""
    cases = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(json.loads(line))
    return cases
