"""Factories for canonical queue jobs and payloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PAYLOAD_ROOT = Path("/app/payloads")
QUEUE_ROOT = Path("/app/queue")


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def make_job(job_id: str, payload: bytes, *, key: str = "release-primary",
             mechanism: str = "rsa-pss-sha256", filename: str | None = None,
             payload_path: Path | None = None) -> dict[str, object]:
    """Write a payload and return its documented queue record."""
    path = payload_path or PAYLOAD_ROOT / f"{job_id}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "schema_version": 1, "job_id": job_id, "payload_path": str(path),
        "payload_sha256": hashlib.sha256(payload).hexdigest(), "key": key,
        "mechanism": mechanism,
    }


def install_job(job: dict[str, object], filename: str | None = None) -> Path:
    """Install a queue file with intentionally ordinary JSON formatting."""
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    path = QUEUE_ROOT / (filename or f"{job['job_id']}.json")
    path.write_text(json.dumps(job, indent=2) + "\n")
    return path


def job_digest(job: dict[str, object]) -> str:
    """Return the canonical job-body digest specified by the job contract."""
    return hashlib.sha256(canonical_json(job)).hexdigest()
