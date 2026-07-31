"""Authoring-time generator for the framekit audit evidence.

Run once from the task root to (re)produce, deterministically:
  - environment/cases.jsonl     the graded evidence, inputs only, no answers
  - environment/examples.jsonl  a disclosed teaching subset that carries answers

Each manifest line is a JSON object: {"id", "config_text", "frame_hex"}, plus
"expected" for the examples file. config_text is the exact build-configuration
text for that case, kept as raw text so malformed-configuration cases can be
represented faithfully. Lives under tests/_devtools, outside the Dockerfile
COPY list, so it never ships to the agent.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_oracle_spec = importlib.util.spec_from_file_location(
    "oracle", ROOT / "tests" / "_lib" / "oracle.py"
)
oracle = importlib.util.module_from_spec(_oracle_spec)
_oracle_spec.loader.exec_module(oracle)

HEADER_SIZE = oracle.HEADER_SIZE
CASES_PATH = ROOT / "environment" / "cases.jsonl"
EXAMPLES_PATH = ROOT / "environment" / "examples.jsonl"


def cfg_text(fpc: bool, sv: str) -> str:
    return json.dumps({"fast_path_compiled": fpc, "source_variant": sv})


def regime1_normal(pad: int, sub_len: int, seed: int) -> bytes:
    outer_len = HEADER_SIZE + pad
    payload = bytes((seed + i) % 256 for i in range(pad))
    return oracle.encode_frame(outer_len, sub_len, 1, payload=payload)


def regime2_zero_body(payload_len: int, seed: int) -> bytes:
    outer_len = HEADER_SIZE + payload_len
    payload = bytes((seed + i) % 256 for i in range(payload_len))
    return oracle.encode_frame(outer_len, payload_len, 1, payload=payload)


def regime3_double_wrap(outer_len: int, sub_len: int, tail: int) -> bytes:
    return oracle.encode_frame(outer_len, sub_len, 1, payload=bytes(range(tail)))


def regime4a_no_wrap_overclaim(claimed_extra: int, tail: int) -> bytes:
    outer_len = HEADER_SIZE + tail + claimed_extra
    return oracle.encode_frame(outer_len, 0, 1, payload=bytes(range(tail)))


def regime4b_single_wrap(outer_len: int, sub_len: int, tail: int) -> bytes:
    return oracle.encode_frame(outer_len, sub_len, 1, payload=bytes(range(tail)))


def build_cases():
    """Return list of (id, config_text, frame_bytes)."""
    cases = []

    # Bad magic: at least header length, dispatch gate wide open.
    for i, bad_magic in enumerate([b"XXXX", b"FK00", b"fk01"]):
        buf = bytearray(regime1_normal(10, 2, i))
        buf[0:4] = bad_magic
        cases.append((f"reject-magic-{i}", cfg_text(True, "original"), bytes(buf)))

    # Outer length above the sanity ceiling.
    for i, over in enumerate([1_000_000_001, 2_000_000_000, 4_000_000_000]):
        buf = oracle.encode_frame(over, 0, 1, payload=bytes(5))
        cases.append(
            (f"reject-outerlen-bound-{i}", cfg_text(True, "original"), buf)
        )

    regime1 = [
        regime1_normal(pad, sub, seed)
        for seed, (pad, sub) in enumerate([(50, 0), (50, 10), (87, 3), (20, 5), (100, 40)])
    ]
    regime2 = [regime2_zero_body(pl, seed) for seed, pl in enumerate([0, 5, 20, 50, 87])]
    regime3 = [
        regime3_double_wrap(ol, sl, 20)
        for ol, sl in [(0, 0), (3, 1), (5, 0), (8, 4), (12, 12)]
    ]
    regime4 = [
        regime4a_no_wrap_overclaim(claimed_extra=500, tail=5),
        regime4a_no_wrap_overclaim(claimed_extra=50_000, tail=10),
        regime4b_single_wrap(outer_len=50, sub_len=1000, tail=37),
        regime4b_single_wrap(outer_len=200, sub_len=10_000, tail=187),
        regime4b_single_wrap(outer_len=13, sub_len=1, tail=0),
    ]
    all_regimes = {"r1": regime1, "r2": regime2, "r3": regime3, "r4": regime4}

    # Fast path fully enabled: the arithmetic decides the verdict.
    for rname, bufs in all_regimes.items():
        for i, buf in enumerate(bufs):
            cases.append((f"allopen-{rname}-{i}", cfg_text(True, "original"), buf))

    # Any one gate closed forces the safe verdict, whatever the arithmetic says.
    gate_off = [("fastoff", False, "original"), ("flagoff", True, "original"), ("guarded", True, "guarded")]
    for rname, bufs in all_regimes.items():
        for cfgname, fpc, sv in gate_off:
            for i, buf in enumerate(bufs[:2]):
                use = buf
                if cfgname == "flagoff":
                    b = bytearray(buf)
                    b[12] &= ~1
                    use = bytes(b)
                cases.append((f"gateoff-{cfgname}-{rname}-{i}", cfg_text(fpc, sv), use))

    # Same reachable-under-original frame, but a closed gate via config only.
    selected = [regime1[0], regime1[1], regime2[0], regime3[0], regime4[0], regime4[2]]
    for i, buf in enumerate(selected):
        cases.append((f"meta-flagoff-{i}", cfg_text(False, "original"), buf))
        cases.append((f"meta-guarded-{i}", cfg_text(True, "guarded"), buf))

    # Big-endian sub_len source data read under the little-endian contract.
    endian_sources = [(50, 10, 40, 0), (200, 10_000, 187, 1), (13, 1, 0, 2), (1000, 0, 5, 3), (0, 0, 20, 4), (50, 300, 37, 5)]
    for outer_len, sub_len, tail, idx in endian_sources:
        buf = oracle.encode_frame(outer_len, sub_len, 1, payload=bytes(range(tail)), sub_len_endian="big")
        cases.append((f"endianswap-{idx}", cfg_text(True, "original"), buf))

    # Malformed: physically short frames, valid configuration.
    good_frame = regime1[0]
    for i, nbytes in enumerate([0, 5, 12]):
        cases.append((f"malformed-short-{i}", cfg_text(True, "original"), good_frame[:nbytes]))

    # Malformed: unparseable or ill-typed configuration, valid frame.
    bad_configs = [
        "{ not json",
        "[]",
        '{"source_variant": "original"}',
        '{"fast_path_compiled": true}',
        '{"fast_path_compiled": true, "source_variant": "bogus"}',
        '{"fast_path_compiled": "yes", "source_variant": "original"}',
    ]
    for i, ct in enumerate(bad_configs):
        cases.append((f"malformed-config-{i}", ct, good_frame))

    return cases


EXAMPLE_SPECS = [
    ("example-reject-magic", "reject-magic-0"),
    ("example-reject-bound", "reject-outerlen-bound-0"),
    ("example-exploitable", "allopen-r4-2"),
    ("example-reachable-safe", "allopen-r1-0"),
    ("example-double-wrap-safe", "allopen-r3-0"),
    ("example-gate-closed", "gateoff-flagoff-r1-0"),
    ("example-guarded", "meta-guarded-0"),
    ("example-malformed-frame", "malformed-short-1"),
    ("example-malformed-config", "malformed-config-0"),
]


def main():
    cases = build_cases()
    by_id = {cid: (ct, fb) for cid, ct, fb in cases}
    assert len(by_id) == len(cases), "duplicate case id"
    assert len(cases) >= 60, f"only {len(cases)} cases, need >= 60"

    with CASES_PATH.open("w") as fh:
        for cid, ct, fb in cases:
            fh.write(json.dumps({"id": cid, "config_text": ct, "frame_hex": fb.hex()}) + "\n")

    with EXAMPLES_PATH.open("w") as fh:
        for ex_id, src_id in EXAMPLE_SPECS:
            ct, fb = by_id[src_id]
            expected = oracle.classify(ct, fb)
            fh.write(
                json.dumps(
                    {"id": ex_id, "config_text": ct, "frame_hex": fb.hex(), "expected": expected}
                )
                + "\n"
            )

    verdict_kinds = {}
    for cid, ct, fb in cases:
        v = oracle.classify(ct, fb).split(":")[0]
        verdict_kinds[v] = verdict_kinds.get(v, 0) + 1
    print(f"cases: {len(cases)}  examples: {len(EXAMPLE_SPECS)}")
    print(f"verdict spread: {verdict_kinds}")


if __name__ == "__main__":
    main()
