"""Strict readers for signingd's canonical published JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .job_factory import canonical_json

OUTPUT = Path("/output/signed")


def read_canonical(path: Path) -> dict[str, object]:
    """Decode JSON and prove its on-disk representation is canonical."""
    raw = path.read_bytes()
    value = json.loads(raw)
    assert raw == canonical_json(value), f"{path} is not canonical JSON"
    return value


def record(job_id: str) -> dict[str, object]:
    return read_canonical(OUTPUT / "jobs" / f"{job_id}.json")


def index() -> dict[str, object]:
    return read_canonical(OUTPUT / "index.json")


def all_records() -> dict[str, dict[str, object]]:
    directory = OUTPUT / "jobs"
    return {path.stem: read_canonical(path) for path in directory.glob("*.json")}
