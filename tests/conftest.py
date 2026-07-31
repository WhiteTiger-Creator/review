"""Minimal CTRF writer for the offline verifier."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def pytest_addoption(parser):
    parser.addoption("--ctrf", action="store", default=None)


def pytest_sessionfinish(session, exitstatus):
    path = session.config.getoption("--ctrf")
    if not path:
        return
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "results": {
            "tool": {"name": "pytest"},
            "summary": {
                "tests": session.testscollected,
                "passed": 0 if exitstatus else session.testscollected,
                "failed": 0 if exitstatus == 0 else 1,
                "pending": 0,
                "skipped": 0,
                "other": 0,
                "start": now,
                "stop": now,
            },
            "tests": [],
        }
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
