"""Cryptographic checks independent of the application implementation."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PUBLIC = Path("/app/config/public")


def fingerprint(pem: Path) -> str:
    key = serialization.load_pem_public_key(pem.read_bytes())
    der = key.public_bytes(serialization.Encoding.DER,
                           serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def verify(record: dict[str, object], payload: bytes, pem: Path) -> None:
    """Verify an RSA signature using the declared PSS or PKCS#1 mechanism."""
    key = serialization.load_pem_public_key(pem.read_bytes())
    signature = base64.b64decode(record["signature_base64"], validate=True)
    if record["mechanism"] == "rsa-pss-sha256":
        algorithm = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32)
    elif record["mechanism"] == "rsa-pkcs1-sha256":
        algorithm = padding.PKCS1v15()
    else:
        raise AssertionError(f"unexpected mechanism {record['mechanism']!r}")
    key.verify(signature, payload, algorithm, hashes.SHA256())
