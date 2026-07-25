"""Independent durable-state fixtures for recovery tests."""

from __future__ import annotations

import json
from pathlib import Path

from .job_factory import canonical_json, job_digest

STATE = Path("/app/state")
OUTPUT = Path("/output/signed")


def write_stage(job: dict[str, object], record: dict[str, object]) -> Path:
    """Write the documented staged-record envelope without application code."""
    path = STATE / "staging" / f"{job['job_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json({"body_digest": job_digest(job), "record": record}))
    return path


def write_final(record: dict[str, object]) -> Path:
    """Write a canonical final job record without adding it to the index."""
    path = OUTPUT / "jobs" / f"{record['job_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(record))
    return path


def write_index(records: list[dict[str, object]]) -> Path:
    """Write a canonical index derived from supplied signed records."""
    jobs = [{"job_id": r["job_id"], "record": f"jobs/{r['job_id']}.json",
             "payload_sha256": r["payload_sha256"],
             "key_fingerprint_sha256": r["key_fingerprint_sha256"]} for r in records]
    jobs.sort(key=lambda r: r["job_id"])
    path = OUTPUT / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json({"schema_version": 1, "jobs": jobs}))
    return path


def write_journal(entries: list[object] | None = None) -> Path:
    """Create a journal file (empty by default) for recovery fixture control."""
    if entries is None:
        entries = []
    path = STATE / "journal.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries))
    return path
