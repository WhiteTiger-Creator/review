"""Independent canonical JSON and RS256 verification."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def sort_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_value(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [sort_value(v) for v in value]
    return value


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(sort_value(payload), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_attestation(body: dict, public_pem: Path | None = None) -> None:
    public_pem = public_pem or FIXTURES / "attestor-public.pem"
    signature = body.pop("signature")
    assert isinstance(signature, dict)
    assert signature.get("alg") == "RS256"
    encoded = signature["value"]
    b64_suffix = "=" * (-len(encoded) % 4)
    sig_bytes = base64.urlsafe_b64decode(encoded + b64_suffix)
    payload = canonical_json_bytes(body)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload_path = root / "payload.bin"
        sig_path = root / "signature.bin"
        payload_path.write_bytes(payload)
        sig_path.write_bytes(sig_bytes)
        proc = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_pem),
                "-signature",
                str(sig_path),
                str(payload_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
