"""Digest helpers mirroring docs/t_policy.rst (sha256 + little-endian packing).

Normative residual, ranking, journal, and seal packing obligations live in
/app/environment/docs/t_policy.rst. digest_hex and seal_hex are 64-character
lowercase hex strings. util_ratio implements joint_use / max(eff, 1e-12).
"""

from __future__ import annotations

import hashlib
import math
import struct


def u32(v: int) -> bytes:
    return struct.pack("<I", v & 0xFFFFFFFF)


def f64(v: float) -> bytes:
    return struct.pack("<d", float(v))


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def util_ratio(use: float, eff: float) -> float:
    return use / max(eff, 1e-12)


def nearly_same(a: float, b: float, tol: float = 1.0e-9) -> bool:
    return math.fabs(a - b) <= tol
