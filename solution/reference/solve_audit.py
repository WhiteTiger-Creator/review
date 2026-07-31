"""Reference audit for the framekit length-underflow task.

Reads the evidence manifest, decides each case against the frame-format
contract, and writes the findings file. Carries its own copy of the dispatch
and wrapping arithmetic so it stands on its own.
"""

import json
import sys
from pathlib import Path

MASK64 = (1 << 64) - 1
HEADER_SIZE = 13
ABSOLUTE_MAX = 1_000_000_000

CASES = Path("/app/environment/cases.jsonl")
OUT = Path("/app/verdicts.txt")


def parse_config(text):
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    fpc = obj.get("fast_path_compiled")
    sv = obj.get("source_variant")
    if not isinstance(fpc, bool) or sv not in ("original", "guarded"):
        return None
    return fpc, sv


def verdict(config_text, frame):
    cfg = parse_config(config_text)
    if cfg is None or len(frame) < HEADER_SIZE:
        return "MALFORMED"
    fpc, sv = cfg
    if frame[0:4] != b"FK01":
        return "REJECT_MAGIC"
    outer_len = int.from_bytes(frame[4:8], "little")
    sub_len = int.from_bytes(frame[8:12], "little")
    flag_byte = frame[12]
    if outer_len > ABSOLUTE_MAX:
        return "REJECT_OUTER_LEN_BOUND"
    if not (fpc and sv == "original" and (flag_byte & 1)):
        return "SAFE_NO_UNSAFE_READ"
    payload_len = (outer_len - HEADER_SIZE) & MASK64
    body_len = (payload_len - sub_len) & MASK64
    end = (HEADER_SIZE + body_len) & MASK64
    if end <= len(frame):
        return "REACHABLE_SAFE"
    return f"REACHABLE_EXPLOITABLE:{HEADER_SIZE}-{end}"


def main():
    lines = []
    for raw in CASES.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        case = json.loads(raw)
        frame = bytes.fromhex(case["frame_hex"])
        lines.append(f"{case['id']} {verdict(case['config_text'], frame)}")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} verdicts to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
