#!/usr/bin/env python3
"""Offline digest helper used by local smoke checks."""

from __future__ import annotations

import hashlib
import sys


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    data = sys.stdin.buffer.read()
    sys.stdout.write(digest_bytes(data) + "\n")


if __name__ == "__main__":
    main()
