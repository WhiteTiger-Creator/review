"""Local probe helper only. Not part of the C++ edit surface.

Mirrors annex seal digest hashing for optional desk-side checks.
"""
import hashlib


def seal_hex(material: bytes) -> str:
    return hashlib.sha256(material).hexdigest()
