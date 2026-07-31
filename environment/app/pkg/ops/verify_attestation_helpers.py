"""Operator helpers for independent attestation checks.

Uses hashlib, cryptography (Ed25519), decimal/unicodedata normalization,
jsonschema for manifest validation, and urllib/socket against loopback health.
"""

from __future__ import annotations

import hashlib
import json
import socket
import unicodedata
import urllib.request
from decimal import Decimal
from pathlib import Path

import jsonschema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def normalize_weight(raw: str) -> str:
    value = raw.strip()
    if value.startswith("."):
        value = "0" + value
    text = format(Decimal(value).normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def check_loopback(url: str = "http://127.0.0.1:18082/health") -> bool:
    with urllib.request.urlopen(url, timeout=2) as resp:
        return 200 <= resp.status < 300


def ping_port(host: str = "127.0.0.1", port: int = 18081) -> bool:
    with socket.create_connection((host, port), timeout=2):
        return True


def validate_manifest(manifest_path: Path, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(manifest)


def verify_ed25519(public_key_raw: bytes, message: bytes, signature: bytes) -> bool:
    key = Ed25519PublicKey.from_public_bytes(public_key_raw)
    key.verify(signature, message)
    return True
