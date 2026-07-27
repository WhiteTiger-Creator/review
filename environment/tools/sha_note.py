"""Offline digest helpers used by diagnostics (not the graded driver)."""

from __future__ import annotations

import hashlib
import struct


def feat_hdr_stamp(blob: bytes) -> int:
    if len(blob) < 12 or blob[:4] != b"FEAT":
        return 0
    _n, _nf, stamp = struct.unpack_from("<HHI", blob, 4)
    return int(stamp)


def short_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]
