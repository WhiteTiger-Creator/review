#!/usr/bin/env python3
"""Reference digest helpers for verifier cross-checks."""
from __future__ import annotations

import hashlib
import struct


def lane_digest(cell: bytes, wave: bytes, masks: dict[int, int], lane_order: list[int], anchor: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(cell)
    hasher.update(wave)
    for slot in lane_order:
        hasher.update(struct.pack("<H", masks.get(slot, 0)))
        hasher.update(struct.pack("<B", slot))
    hasher.update(anchor[:8])
    return hasher.hexdigest()
