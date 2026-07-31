"""Digest helpers shared with the evaluator."""

from __future__ import annotations

import hashlib
import sys


def digest_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest16(data: bytes) -> str:
    return digest_hex(data)[:16]


if __name__ == "__main__":
    payload = sys.stdin.buffer.read()
    sys.stdout.write(digest_hex(payload))
