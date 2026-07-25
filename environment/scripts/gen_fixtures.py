#!/usr/bin/env python3
"""Generate binary pack fixtures for service-restart-storm-budget."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(arms: list[tuple[int, int, int, int, int]]) -> bytes:
    out = b"CELL\x01" + bytes([len(arms)])
    for arm_id, kind, mask, shadow, seq in arms:
        out += bytes([arm_id, kind])
        out += struct.pack("<H", mask)
        out += bytes([shadow, seq])
    return out


def wave(rows: list[int]) -> bytes:
    out = b"WAVE" + struct.pack("<H", len(rows))
    out += bytes(rows)
    return out


def main() -> None:
    pack = ROOT / "pack"
    (pack / "w8").mkdir(parents=True, exist_ok=True)
    (pack / "incidents").mkdir(parents=True, exist_ok=True)
    (pack / "seed").mkdir(parents=True, exist_ok=True)
    (pack / "ledger").mkdir(parents=True, exist_ok=True)
    (pack / "policy").mkdir(parents=True, exist_ok=True)
    (pack / "checkpoints").mkdir(parents=True, exist_ok=True)

    # Include id=2 has abs(2-1)=1 vs exclude shadow_link=1: survives R=2, suppressed at R=1.
    (pack / "w8" / "sg.slice").write_bytes(
        cell(
            [
                (1, 1, 0x0F, 0, 1),
                (2, 1, 0x30, 0, 2),
                (9, 2, 0x30, 1, 0),
                (3, 1, 0x31, 0, 3),
                (4, 1, 0x03, 0, 4),
            ]
        )
    )
    (pack / "w8" / "sd.slice").write_bytes(
        cell(
            [
                (1, 1, 0x11, 0, 1),
                (2, 1, 0x22, 0, 2),
                (9, 2, 0x22, 1, 0),
                (3, 1, 0x44, 0, 3),
                (5, 1, 0x08, 0, 5),
            ]
        )
    )
    (pack / "incidents" / "sg.inc").write_bytes(
        wave([0x0F, 0x30, 0x33, 0xC0, 0x03, 0x11])
    )
    (pack / "incidents" / "sd.inc").write_bytes(
        wave([0x11, 0x22, 0x33, 0x44, 0x08, 0x0F])
    )

    seed = b"N3ANCHOR" + bytes([0x5A, 0xA5, 0x3C, 0xC3])
    (pack / "seed" / "token_seed.bin").write_bytes(seed)
    (pack / "seed" / ".storm_gen").write_text("0", encoding="utf-8")

    waves = [
        {"gen": 0, "family": "core", "unit": "sg", "tomb": False},
        {"gen": 1, "family": "decoy", "unit": "sd", "tomb": True},
    ]
    waves_text = "\n".join(json.dumps(w, separators=(",", ":")) for w in waves) + "\n"
    (pack / "ledger" / "waves.ndjson").write_text(waves_text, encoding="utf-8")
    (pack / "checkpoints" / "waves_clean.ndjson").write_text(waves_text, encoding="utf-8")

    ov0 = {"gen": 0, "shadow_radius": 2, "policy_id": "ov_base"}
    ov1 = {"gen": 1, "shadow_radius": 1, "policy_id": "ov_decoy"}
    (pack / "policy" / "ov_g0.json").write_text(
        json.dumps(ov0, indent=2) + "\n", encoding="utf-8"
    )
    (pack / "policy" / "ov_g1.json").write_text(
        json.dumps(ov1, indent=2) + "\n", encoding="utf-8"
    )

    # Gen-bound staging: g0 matches cold seed; g1 is divergent decoy.
    (pack / "checkpoints" / "stg_g0.bin").write_bytes(seed[:8])
    (pack / "checkpoints" / "stg_g1.bin").write_bytes(b"HOTSTG01")

    print("fixtures written")
    print("ledger_fp", hashlib.sha256(waves_text.encode()).hexdigest())


if __name__ == "__main__":
    main()
