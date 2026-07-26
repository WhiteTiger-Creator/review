"""Offline digest helper note: verifier may import hashlib for sha256 checks."""
import hashlib


def hex8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]
