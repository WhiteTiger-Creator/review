"""Verify hidden fixture checksums before use."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_fixture_checksums() -> None:
    manifest = json.loads((FIXTURES / "fixture-checksums.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = FIXTURES / name
        actual = sha256_file(path)
        if actual != expected:
            raise AssertionError(f"checksum mismatch for {name}: {actual} != {expected}")
