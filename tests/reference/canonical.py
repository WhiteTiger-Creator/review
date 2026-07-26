"""Canonical JSON + SHA-256 helpers for the recovery profile."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest_of(value: Any) -> str:
    return sha256_hex(canonical_dumps(value))
